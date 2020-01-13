#  Polkascan PRE Harvester
#
#  Copyright 2018-2019 openAware BV (NL).
#  This file is part of Polkascan.
#
#  Polkascan is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Polkascan is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Polkascan. If not, see <http://www.gnu.org/licenses/>.
#
#  event.py
#
from packaging import version

from app.models.data import Account, AccountIndex, DemocracyProposal, Contract, Session, AccountAudit, \
    AccountIndexAudit, DemocracyProposalAudit, SessionTotal, SessionValidator, DemocracyReferendumAudit, RuntimeStorage, \
    SessionNominator, RuntimeCall, CouncilMotionAudit, CouncilVoteAudit, TechCommProposalAudit, \
    TechCommProposalVoteAudit, TreasuryProposalAudit, Trade
from app.processors.base import EventProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_NEW, ACCOUNT_AUDIT_TYPE_REAPED, ACCOUNT_INDEX_AUDIT_TYPE_NEW, \
    ACCOUNT_INDEX_AUDIT_TYPE_REAPED, DEMOCRACY_PROPOSAL_AUDIT_TYPE_PROPOSED, DEMOCRACY_PROPOSAL_AUDIT_TYPE_TABLED, \
    SUBSTRATE_RPC_URL, DEMOCRACY_REFERENDUM_AUDIT_TYPE_STARTED, DEMOCRACY_REFERENDUM_AUDIT_TYPE_PASSED, \
    DEMOCRACY_REFERENDUM_AUDIT_TYPE_NOTPASSED, DEMOCRACY_REFERENDUM_AUDIT_TYPE_CANCELLED, \
    DEMOCRACY_REFERENDUM_AUDIT_TYPE_EXECUTED, LEGACY_SESSION_VALIDATOR_LOOKUP, SUBSTRATE_METADATA_VERSION, \
    COUNCIL_MOTION_TYPE_PROPOSED, COUNCIL_MOTION_TYPE_APPROVED, COUNCIL_MOTION_TYPE_DISAPPROVED, \
    COUNCIL_MOTION_TYPE_EXECUTED, TECHCOMM_PROPOSAL_TYPE_PROPOSED, TECHCOMM_PROPOSAL_TYPE_APPROVED, \
    TECHCOMM_PROPOSAL_TYPE_DISAPPROVED, TECHCOMM_PROPOSAL_TYPE_EXECUTED, TREASURY_PROPOSAL_TYPE_PROPOSED, \
    TREASURY_PROPOSAL_TYPE_AWARDED, TREASURY_PROPOSAL_TYPE_REJECTED
from app.utils.ss58 import ss58_encode
from scalecodec import ScaleBytes, Proposal
from scalecodec.base import ScaleDecoder
from scalecodec.exceptions import RemainingScaleBytesNotEmptyException
from substrateinterface import SubstrateInterface


class NewSessionEventProcessor(EventProcessor):

    module_id = 'session'
    event_id = 'NewSession'

    def add_session(self, db_session, session_id):
        current_era = None
        validators = []
        nominators = []
        validation_session_lookup = {}

        substrate = SubstrateInterface(SUBSTRATE_RPC_URL)

        # Retrieve current era
        storage_call = RuntimeStorage.query(db_session).filter_by(
            module_id='staking',
            name='CurrentEra',
            spec_version=self.block.spec_version_id
        ).first()

        if storage_call:
            try:
                current_era = substrate.get_storage(
                    block_hash=self.block.hash,
                    module="Staking",
                    function="CurrentEra",
                    return_scale_type=storage_call.get_return_type(),
                    hasher=storage_call.type_hasher,
                    metadata_version=SUBSTRATE_METADATA_VERSION
                )
            except RemainingScaleBytesNotEmptyException:
                pass

        # Retrieve validators for new session from storage

        storage_call = RuntimeStorage.query(db_session).filter_by(
            module_id='session',
            name='Validators',
            spec_version=self.block.spec_version_id
        ).first()

        if storage_call:
            try:
                validators = substrate.get_storage(
                    block_hash=self.block.hash,
                    module="Session",
                    function="Validators",
                    return_scale_type=storage_call.get_return_type(),
                    hasher=storage_call.type_hasher,
                    metadata_version=SUBSTRATE_METADATA_VERSION
                ) or []
            except RemainingScaleBytesNotEmptyException:
                pass

        # Retrieve all sessions in one call
        if not LEGACY_SESSION_VALIDATOR_LOOKUP:

            # Retrieve session account
            # TODO move to network specific data types
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='session',
                name='QueuedKeys',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:
                try:
                    validator_session_list = substrate.get_storage(
                        block_hash=self.block.hash,
                        module="Session",
                        function="QueuedKeys",
                        return_scale_type=storage_call.get_return_type(),
                        hasher=storage_call.type_hasher,
                        metadata_version=SUBSTRATE_METADATA_VERSION
                    ) or []
                except RemainingScaleBytesNotEmptyException:

                    try:
                        validator_session_list = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Session",
                            function="QueuedKeys",
                            return_scale_type='Vec<(ValidatorId, LegacyKeys)>',
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or []
                    except RemainingScaleBytesNotEmptyException:
                        validator_session_list = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Session",
                            function="QueuedKeys",
                            return_scale_type='Vec<(ValidatorId, EdgewareKeys)>',
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or []

                # build lookup dict
                validation_session_lookup = {}
                for validator_session_item in validator_session_list:
                    session_key = ''

                    if validator_session_item['keys'].get('grandpa'):
                        session_key = validator_session_item['keys'].get('grandpa')

                    if validator_session_item['keys'].get('ed25519'):
                        session_key = validator_session_item['keys'].get('ed25519')

                    validation_session_lookup[
                        validator_session_item['validator'].replace('0x', '')] = session_key.replace('0x', '')

        for rank_nr, validator_account in enumerate(validators):
            validator_stash = None
            validator_controller = None
            validator_ledger = {}
            validator_prefs = {}
            validator_session = ''
            exposure = {}

            if not LEGACY_SESSION_VALIDATOR_LOOKUP:
                validator_stash = validator_account.replace('0x', '')

                # Retrieve stash account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='staking',
                    name='Bonded',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        validator_controller = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Staking",
                            function="Bonded",
                            params=validator_stash,
                            return_scale_type=storage_call.get_return_type(),
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or ''

                        validator_controller = validator_controller.replace('0x', '')

                    except RemainingScaleBytesNotEmptyException:
                        pass

                # Retrieve session account
                validator_session = validation_session_lookup.get(validator_stash)

            else:
                validator_controller = validator_account.replace('0x', '')

                # Retrieve stash account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='staking',
                    name='Ledger',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        validator_ledger = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Staking",
                            function="Ledger",
                            params=validator_controller,
                            return_scale_type=storage_call.get_return_type(),
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or {}

                        validator_stash = validator_ledger.get('stash', '').replace('0x', '')

                    except RemainingScaleBytesNotEmptyException:
                        pass

                # Retrieve session account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='session',
                    name='NextKeyFor',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        validator_session = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Session",
                            function="NextKeyFor",
                            params=validator_controller,
                            return_scale_type=storage_call.get_return_type(),
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or ''
                    except RemainingScaleBytesNotEmptyException:
                        pass

                    validator_session = validator_session.replace('0x', '')

            # Retrieve validator preferences for stash account
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='staking',
                name='Validators',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:
                try:
                    validator_prefs = substrate.get_storage(
                        block_hash=self.block.hash,
                        module="Staking",
                        function="Validators",
                        params=validator_stash,
                        return_scale_type=storage_call.get_return_type(),
                        hasher=storage_call.type_hasher,
                        metadata_version=SUBSTRATE_METADATA_VERSION
                    ) or {'col1': {}, 'col2': {}}
                except RemainingScaleBytesNotEmptyException:
                    pass

            # Retrieve nominators
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='staking',
                name='Stakers',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:
                try:
                    exposure = substrate.get_storage(
                        block_hash=self.block.hash,
                        module="Staking",
                        function="Stakers",
                        params=validator_stash,
                        return_scale_type=storage_call.get_return_type(),
                        hasher=storage_call.type_hasher,
                        metadata_version=SUBSTRATE_METADATA_VERSION
                    ) or {}
                except RemainingScaleBytesNotEmptyException:
                    pass

            if exposure.get('total'):
                bonded_nominators = exposure.get('total') - exposure.get('own')
            else:
                bonded_nominators = None

            session_validator = SessionValidator(
                session_id=session_id,
                validator_controller=validator_controller,
                validator_stash=validator_stash,
                bonded_total=exposure.get('total'),
                bonded_active=validator_ledger.get('active'),
                bonded_own=exposure.get('own'),
                bonded_nominators=bonded_nominators,
                validator_session=validator_session,
                rank_validator=rank_nr,
                unlocking=validator_ledger.get('unlocking'),
                count_nominators=len(exposure.get('others', [])),
                unstake_threshold=validator_prefs.get('col1', {}).get('unstakeThreshold'),
                commission=validator_prefs.get('col1', {}).get('validatorPayment')
            )

            session_validator.save(db_session)

            # Store nominators
            for rank_nominator, nominator_info in enumerate(exposure.get('others', [])):
                nominator_stash = nominator_info.get('who').replace('0x', '')
                nominators.append(nominator_stash)

                session_nominator = SessionNominator(
                    session_id=session_id,
                    rank_validator=rank_nr,
                    rank_nominator=rank_nominator,
                    nominator_stash=nominator_stash,
                    bonded=nominator_info.get('value'),
                )

                session_nominator.save(db_session)

        # Store session
        session = Session(
            id=session_id,
            start_at_block=self.block.id + 1,
            created_at_block=self.block.id,
            created_at_extrinsic=self.event.extrinsic_idx,
            created_at_event=self.event.event_idx,
            count_validators=len(validators),
            count_nominators=len(set(nominators)),
            era=current_era
        )

        session.save(db_session)

        # Retrieve previous session to calculate count_blocks
        prev_session = Session.query(db_session).filter_by(id=session_id - 1).first()

        if prev_session:
            count_blocks = self.block.id - prev_session.start_at_block + 1
        else:
            count_blocks = self.block.id

        session_total = SessionTotal(
            id=session_id - 1,
            end_at_block=self.block.id,
            count_blocks=count_blocks
        )

        session_total.save(db_session)

    def accumulation_hook(self, db_session):
        self.block.count_sessions_new += 1

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        session_id = self.event.attributes[0]['value']
        self.add_session(db_session, session_id)


class NewAccountEventProcessor(EventProcessor):

    module_id = 'balances'
    event_id = 'NewAccount'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and self.event.attributes[1]['type'] == 'Balance':

            account_id = self.event.attributes[0]['value'].replace('0x', '')
            balance = self.event.attributes[1]['value']

            self.block._accounts_new.append(account_id)

            account_audit = AccountAudit(
                account_id=account_id,
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=ACCOUNT_AUDIT_TYPE_NEW
            )

            account_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class ReapedAccount(EventProcessor):
    module_id = 'balances'
    event_id = 'ReapedAccount'

    def accumulation_hook(self, db_session):
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'AccountId':

            account_id = self.event.attributes[0]['value'].replace('0x', '')

            self.block._accounts_reaped.append(account_id)

            account_audit = AccountAudit(
                account_id=account_id,
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=ACCOUNT_AUDIT_TYPE_REAPED
            )

            account_audit.save(db_session)

            # Insert account index audit record

            new_account_index_audit = AccountIndexAudit(
                account_index_id=None,
                account_id=account_id,
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=ACCOUNT_INDEX_AUDIT_TYPE_REAPED
            )

            new_account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):

        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class NewAccountIndexEventProcessor(EventProcessor):

    module_id = 'indices'
    event_id = 'NewAccountIndex'

    def accumulation_hook(self, db_session):

        account_id = self.event.attributes[0]['value'].replace('0x', '')
        id = self.event.attributes[1]['value']

        account_index_audit = AccountIndexAudit(
            account_index_id=id,
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_INDEX_AUDIT_TYPE_NEW
        )

        account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class ProposedEventProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Proposed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'PropIndex' and self.event.attributes[1]['type'] == 'Balance':

            proposal_audit = DemocracyProposalAudit(
                democracy_proposal_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_PROPOSAL_AUDIT_TYPE_PROPOSED
            )

            proposal_audit.data = {'bond': self.event.attributes[1]['value'], 'proposal': None}

            for param in self.extrinsic.params:
                if param.get('name') == 'proposal':
                    proposal_audit.data['proposal'] = param.get('value')

            proposal_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyTabledEventProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Tabled'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 3 and self.event.attributes[0]['type'] == 'PropIndex' \
                and self.event.attributes[1]['type'] == 'Balance' and \
                self.event.attributes[2]['type'] == 'Vec<AccountId>':

            proposal_audit = DemocracyProposalAudit(
                democracy_proposal_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_PROPOSAL_AUDIT_TYPE_TABLED
            )
            proposal_audit.data = {'bond': self.event.attributes[1]['value'], 'proposal': None}

            proposal_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyStartedProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Started'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'ReferendumIndex' and \
                self.event.attributes[1]['type'] == 'VoteThreshold':

            # Retrieve proposal from storage
            substrate = SubstrateInterface(SUBSTRATE_RPC_URL)
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='democracy',
                name='ReferendumInfoOf',
            ).order_by(RuntimeStorage.spec_version.desc()).first()

            proposal = substrate.get_storage(
                block_hash=self.block.hash,
                module='Democracy',
                function='ReferendumInfoOf',
                params=self.event.attributes[0]['valueRaw'],
                return_scale_type=storage_call.type_value,
                hasher=storage_call.type_hasher,
                metadata=self.metadata,
                metadata_version=SUBSTRATE_METADATA_VERSION
            )

            if proposal.get('proposalHash'):
                # Retrieve proposal by hash
                substrate = SubstrateInterface(SUBSTRATE_RPC_URL)
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='democracy',
                    name='Preimages',
                ).order_by(RuntimeStorage.spec_version.desc()).first()

                proposal_preimage = substrate.get_storage(
                    block_hash=self.block.hash,
                    module='Democracy',
                    function='Preimages',
                    params=proposal.get('proposalHash').replace('0x', ''),
                    return_scale_type=storage_call.type_value,
                    hasher=storage_call.type_hasher,
                    metadata=self.metadata,
                    metadata_version=SUBSTRATE_METADATA_VERSION
                )

                if proposal_preimage:
                    proposal.update(proposal_preimage)

                if proposal.get('proposal') and proposal['proposal'].get('call_index'):
                    # Retrieve the documentation of the proposal call
                    call_data = self.metadata.call_index.get(proposal['proposal'].get('call_index'))

                    if call_data:
                        proposal['proposal']['call_documentation'] = '\n'.join(call_data[1].docs)

            referendum_audit = DemocracyReferendumAudit(
                democracy_referendum_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_REFERENDUM_AUDIT_TYPE_STARTED,
                data={
                    'vote_threshold': self.event.attributes[1]['value'],
                    'ReferendumIndex': self.event.attributes[0]['valueRaw'],
                    'proposal': proposal
                }
            )

            referendum_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyPassedProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Passed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'ReferendumIndex':

            referendum_audit = DemocracyReferendumAudit(
                democracy_referendum_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_REFERENDUM_AUDIT_TYPE_PASSED
            )

            referendum_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyNotPassedProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'NotPassed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'ReferendumIndex':

            referendum_audit = DemocracyReferendumAudit(
                democracy_referendum_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_REFERENDUM_AUDIT_TYPE_NOTPASSED
            )

            referendum_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyCancelledProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Cancelled'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'ReferendumIndex':

            referendum_audit = DemocracyReferendumAudit(
                democracy_referendum_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_REFERENDUM_AUDIT_TYPE_CANCELLED
            )

            referendum_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class DemocracyExecutedProcessor(EventProcessor):

    module_id = 'democracy'
    event_id = 'Executed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'ReferendumIndex' and \
                self.event.attributes[1]['type'] == 'bool':

            referendum_audit = DemocracyReferendumAudit(
                democracy_referendum_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=DEMOCRACY_REFERENDUM_AUDIT_TYPE_EXECUTED,
                data={'success': self.event.attributes[1]['value']}
            )

            referendum_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CouncilMotionProposedEventProcessor(EventProcessor):

    module_id = 'council'
    event_id = 'Proposed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 4 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'ProposalIndex' and \
                self.event.attributes[2]['type'] == 'Hash' and \
                self.event.attributes[3]['type'] == 'MemberCount':

            motion_audit = CouncilMotionAudit(
                motion_hash=self.event.attributes[2]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=COUNCIL_MOTION_TYPE_PROPOSED
            )

            motion_audit.data = {
                'proposalIndex': self.event.attributes[1]['value'],
                'proposedBy': self.event.attributes[0]['value'],
                'threshold': self.event.attributes[3]['value'],
                'proposal': None
            }

            for param in self.extrinsic.params:
                if param.get('name') == 'proposal':
                    motion_audit.data['proposal'] = param.get('value')

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in CouncilMotionAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CouncilMotionApprovedEventProcessor(EventProcessor):

    module_id = 'council'
    event_id = 'Approved'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and self.event.attributes[0]['type'] == 'Hash':

            motion_audit = CouncilMotionAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=COUNCIL_MOTION_TYPE_APPROVED
            )

            motion_audit.data = {
                'approved': True
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in CouncilMotionAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CouncilMotionDisapprovedEventProcessor(EventProcessor):

    module_id = 'council'
    event_id = 'Disapproved'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and self.event.attributes[0]['type'] == 'Hash':

            motion_audit = CouncilMotionAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=COUNCIL_MOTION_TYPE_DISAPPROVED
            )

            motion_audit.data = {
                'approved': False
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in CouncilMotionAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CouncilMotionExecutedEventProcessor(EventProcessor):

    module_id = 'council'
    event_id = 'Executed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'Hash' and \
                self.event.attributes[1]['type'] == 'bool':

            motion_audit = CouncilMotionAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=COUNCIL_MOTION_TYPE_EXECUTED
            )

            motion_audit.data = {
                'executed': True
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in CouncilMotionAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CouncilMotionVotedEventProcessor(EventProcessor):

    module_id = 'council'
    event_id = 'Voted'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 5 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'Hash' and \
                self.event.attributes[2]['type'] == 'bool' and \
                self.event.attributes[3]['type'] == 'MemberCount' and \
                self.event.attributes[4]['type'] == 'MemberCount':

            vote_audit = CouncilVoteAudit(
                motion_hash=self.event.attributes[1]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx
            )

            vote_audit.data = {
                'vote': self.event.attributes[2]['value'],
                'account_id': self.event.attributes[0]['value'],
                'yes_votes_count': self.event.attributes[3]['value'],
                'no_votes_count': self.event.attributes[4]['value']
            }

            vote_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in CouncilVoteAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TechCommProposedEventProcessor(EventProcessor):

    module_id = 'technicalcommittee'
    event_id = 'Proposed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 4 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'ProposalIndex' and \
                self.event.attributes[2]['type'] == 'Hash' and \
                self.event.attributes[3]['type'] == 'MemberCount':

            motion_audit = TechCommProposalAudit(
                motion_hash=self.event.attributes[2]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TECHCOMM_PROPOSAL_TYPE_PROPOSED
            )

            motion_audit.data = {
                'proposalIndex': self.event.attributes[1]['value'],
                'proposedBy': self.event.attributes[0]['value'],
                'threshold': self.event.attributes[3]['value'],
                'proposal': None
            }

            for param in self.extrinsic.params:
                if param.get('name') == 'proposal':
                    motion_audit.data['proposal'] = param.get('value')

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TechCommProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TechCommApprovedEventProcessor(EventProcessor):

    module_id = 'technicalcommittee'
    event_id = 'Approved'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and self.event.attributes[0]['type'] == 'Hash':

            motion_audit = TechCommProposalAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TECHCOMM_PROPOSAL_TYPE_APPROVED
            )

            motion_audit.data = {
                'approved': True
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TechCommProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TechCommDisapprovedEventProcessor(EventProcessor):

    module_id = 'technicalcommittee'
    event_id = 'Disapproved'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and self.event.attributes[0]['type'] == 'Hash':

            motion_audit = TechCommProposalAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TECHCOMM_PROPOSAL_TYPE_DISAPPROVED
            )

            motion_audit.data = {
                'approved': False
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TechCommProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TechCommExecutedEventProcessor(EventProcessor):

    module_id = 'technicalcommittee'
    event_id = 'Executed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'Hash' and \
                self.event.attributes[1]['type'] == 'bool':

            motion_audit = TechCommProposalAudit(
                motion_hash=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TECHCOMM_PROPOSAL_TYPE_EXECUTED
            )

            motion_audit.data = {
                'executed': True
            }

            motion_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TechCommProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TechCommVotedEventProcessor(EventProcessor):

    module_id = 'technicalcommittee'
    event_id = 'Voted'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 5 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'Hash' and \
                self.event.attributes[2]['type'] == 'bool' and \
                self.event.attributes[3]['type'] == 'MemberCount' and \
                self.event.attributes[4]['type'] == 'MemberCount':

            vote_audit = TechCommProposalVoteAudit(
                motion_hash=self.event.attributes[1]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx
            )

            vote_audit.data = {
                'vote': self.event.attributes[2]['value'],
                'account_id': self.event.attributes[0]['value'],
                'yes_votes_count': self.event.attributes[3]['value'],
                'no_votes_count': self.event.attributes[4]['value']
            }

            vote_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TechCommProposalVoteAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TreasuryProposedEventProcessor(EventProcessor):

    module_id = 'treasury'
    event_id = 'Proposed'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'ProposalIndex':

            proposal_audit = TreasuryProposalAudit(
                proposal_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TREASURY_PROPOSAL_TYPE_PROPOSED
            )

            proposal_audit.data = {
                'proposedBy': self.extrinsic.address,
                'beneficiary': None,
                'value': None
            }

            for param in self.extrinsic.params:
                if param.get('name') == 'value':
                    proposal_audit.data['value'] = param.get('value')

                if param.get('name') == 'beneficiary':
                    proposal_audit.data['beneficiary'] = param.get('value')

            proposal_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TreasuryProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TreasuryAwardedEventProcessor(EventProcessor):

    module_id = 'treasury'
    event_id = 'Awarded'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 3 and \
                self.event.attributes[0]['type'] == 'ProposalIndex' and \
                self.event.attributes[1]['type'] == 'Balance' and \
                self.event.attributes[2]['type'] == 'AccountId':

            proposal_audit = TreasuryProposalAudit(
                proposal_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TREASURY_PROPOSAL_TYPE_AWARDED
            )

            proposal_audit.data = {
                'beneficiary': self.event.attributes[2]['value'].replace('0x', ''),
                'value': self.event.attributes[1]['value']
            }

            proposal_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TreasuryProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class TreasuryRejectedEventProcessor(EventProcessor):

    module_id = 'treasury'
    event_id = 'Rejected'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'ProposalIndex' and \
                self.event.attributes[1]['type'] == 'Balance':

            proposal_audit = TreasuryProposalAudit(
                proposal_id=self.event.attributes[0]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=TREASURY_PROPOSAL_TYPE_REJECTED
            )

            proposal_audit.data = {
                'slash_value': self.event.attributes[1]['value']
            }

            proposal_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in TreasuryProposalAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class CodeStoredEventProcessor(EventProcessor):

    module_id = 'contract'
    event_id = 'CodeStored'

    def accumulation_hook(self, db_session):

        self.block.count_contracts_new += 1

        contract = Contract(
            code_hash=self.event.attributes[0]['value'].replace('0x', ''),
            created_at_block=self.event.block_id,
            created_at_extrinsic=self.event.extrinsic_idx,
            created_at_event=self.event.event_idx,
        )

        for param in self.extrinsic.params:
            if param.get('name') == 'code':
                contract.bytecode = param.get('value')

        contract.save(db_session)

    def accumulation_revert(self, db_session):
        for item in Contract.query(db_session).filter_by(created_at_block=self.block.id):
            db_session.delete(item)


class TradeEventProcessor(EventProcessor):

    module_id = 'trademodule'
    event_id = 'TradeCreated'

    def accumulation_hook(self, db_session):
        trade = Trade(
            trade_hash = self.event.attributes[3]['valueRaw'],
            block_id = self.event.block_id,
            extrinsic_idx = self.event.extrinsic_idx,
            event_idx = self.event.event_idx,
            base = self.event.attributes[1]['valueRaw'],
            quote = self.event.attributes[2]['valueRaw'],
            buyer = self.event.attributes[4]['value']['buyer'].replace('0x', ''),
            seller = self.event.attributes[4]['value']['seller'].replace('0x', ''),
            maker = self.event.attributes[4]['value']['maker'].replace('0x', ''),
            taker = self.event.attributes[4]['value']['taker'].replace('0x', ''),
            otype = self.event.attributes[4]['value']['otype'],
            price = self.event.attributes[4]['value']['price'],
            base_amount = self.event.attributes[4]['value']['base_amount'],
            quote_amount = self.event.attributes[4]['value']['quote_amount']
        )

        trade.save(db_session)

    def accumulation_revert(self, db_session):
        for item in Trade.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
