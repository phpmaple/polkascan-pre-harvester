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
#  block.py
#
import datetime

import dateutil
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import func

from app.models.data import Log, AccountAudit, Account, AccountIndexAudit, AccountIndex, DemocracyProposalAudit, \
    DemocracyProposal, DemocracyReferendumAudit, DemocracyReferendum, DemocracyVoteAudit, DemocracyVote, \
    CouncilMotionAudit, CouncilMotion, CouncilVoteAudit, CouncilVote, TechCommProposal, TechCommProposalAudit, \
    TechCommProposalVoteAudit, TechCommProposalVote, TreasuryProposalAudit, TreasuryProposal, Block, Trade, MarketHistory_1m, MarketHistory_5m, MarketHistory_1h, MarketHistory_1d
from app.settings import ACCOUNT_AUDIT_TYPE_NEW, ACCOUNT_AUDIT_TYPE_REAPED, ACCOUNT_INDEX_AUDIT_TYPE_NEW, \
    ACCOUNT_INDEX_AUDIT_TYPE_REAPED, DEMOCRACY_PROPOSAL_AUDIT_TYPE_PROPOSED, DEMOCRACY_PROPOSAL_AUDIT_TYPE_TABLED, \
    DEMOCRACY_REFERENDUM_AUDIT_TYPE_STARTED, DEMOCRACY_REFERENDUM_AUDIT_TYPE_PASSED, \
    DEMOCRACY_REFERENDUM_AUDIT_TYPE_NOTPASSED, DEMOCRACY_REFERENDUM_AUDIT_TYPE_CANCELLED, \
    DEMOCRACY_REFERENDUM_AUDIT_TYPE_EXECUTED, SUBSTRATE_ADDRESS_TYPE, DEMOCRACY_VOTE_AUDIT_TYPE_NORMAL, \
    DEMOCRACY_VOTE_AUDIT_TYPE_PROXY, COUNCIL_MOTION_TYPE_PROPOSED, COUNCIL_MOTION_TYPE_APPROVED, \
    COUNCIL_MOTION_TYPE_DISAPPROVED, COUNCIL_MOTION_TYPE_EXECUTED, TECHCOMM_PROPOSAL_TYPE_PROPOSED, \
    TECHCOMM_PROPOSAL_TYPE_APPROVED, TECHCOMM_PROPOSAL_TYPE_DISAPPROVED, TECHCOMM_PROPOSAL_TYPE_EXECUTED, \
    TREASURY_PROPOSAL_TYPE_PROPOSED, TREASURY_PROPOSAL_TYPE_AWARDED, TREASURY_PROPOSAL_TYPE_REJECTED
from app.utils.ss58 import ss58_encode, ss58_encode_account_index
from scalecodec.base import ScaleBytes

from app.processors.base import BlockProcessor
from scalecodec.block import LogDigest


class LogBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):

        self.block.count_log = len(self.block.logs)

        for idx, log_data in enumerate(self.block.logs):
            log_digest = LogDigest(ScaleBytes(log_data))
            log_digest.decode()

            log = Log(
                block_id=self.block.id,
                log_idx=idx,
                type_id=log_digest.index,
                type=log_digest.index_value,
                data=log_digest.value,
            )

            log.save(db_session)

    def accumulation_revert(self, db_session):
        for item in Log.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class BlockTotalProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        if not parent_sequenced_block_data:
            parent_sequenced_block_data = {}

        if parent_block_data and parent_block_data['datetime']:
            self.sequenced_block.parent_datetime = parent_block_data['datetime']

            if type(parent_block_data['datetime']) is str:
                self.sequenced_block.blocktime = (
                    self.block.datetime - dateutil.parser.parse(parent_block_data['datetime'])).total_seconds()
            else:
                self.sequenced_block.blocktime = (
                    self.block.datetime - parent_block_data['datetime']).total_seconds()
        else:
            self.sequenced_block.blocktime = 0
            self.sequenced_block.parent_datetime = self.block.datetime

        self.sequenced_block.total_extrinsics = int(parent_sequenced_block_data.get(
            'total_extrinsics', 0)) + self.block.count_extrinsics
        self.sequenced_block.total_extrinsics_success = int(parent_sequenced_block_data.get(
            'total_extrinsics_success', 0)) + self.block.count_extrinsics_success
        self.sequenced_block.total_extrinsics_error = int(parent_sequenced_block_data.get(
            'total_extrinsics_error', 0)) + self.block.count_extrinsics_error
        self.sequenced_block.total_extrinsics_signed = int(parent_sequenced_block_data.get(
            'total_extrinsics_signed', 0)) + self.block.count_extrinsics_signed
        self.sequenced_block.total_extrinsics_unsigned = int(parent_sequenced_block_data.get(
            'total_extrinsics_unsigned', 0)) + self.block.count_extrinsics_unsigned
        self.sequenced_block.total_extrinsics_signedby_address = int(parent_sequenced_block_data.get(
            'total_extrinsics_signedby_address', 0)) + self.block.count_extrinsics_signedby_address
        self.sequenced_block.total_extrinsics_signedby_index = int(parent_sequenced_block_data.get(
            'total_extrinsics_signedby_index', 0)) + self.block.count_extrinsics_signedby_index
        self.sequenced_block.total_events = int(
            parent_sequenced_block_data.get('total_events', 0)) + self.block.count_events
        self.sequenced_block.total_events_system = int(parent_sequenced_block_data.get(
            'total_events_system', 0)) + self.block.count_events_system
        self.sequenced_block.total_events_module = int(parent_sequenced_block_data.get(
            'total_events_module', 0)) + self.block.count_events_module
        self.sequenced_block.total_events_extrinsic = int(parent_sequenced_block_data.get(
            'total_events_extrinsic', 0)) + self.block.count_events_extrinsic
        self.sequenced_block.total_events_finalization = int(parent_sequenced_block_data.get(
            'total_events_finalization', 0)) + self.block.count_events_finalization
        self.sequenced_block.total_blocktime = int(parent_sequenced_block_data.get(
            'total_blocktime', 0)) + self.sequenced_block.blocktime
        self.sequenced_block.total_accounts_new = int(parent_sequenced_block_data.get(
            'total_accounts_new', 0)) + self.block.count_accounts_new

        self.sequenced_block.total_logs = int(
            parent_sequenced_block_data.get('total_logs', 0)) + self.block.count_log
        self.sequenced_block.total_accounts = int(parent_sequenced_block_data.get(
            'total_accounts', 0)) + self.block.count_accounts
        self.sequenced_block.total_accounts_reaped = int(parent_sequenced_block_data.get(
            'total_accounts_reaped', 0)) + self.block.count_accounts_reaped
        self.sequenced_block.total_sessions_new = int(parent_sequenced_block_data.get(
            'total_sessions_new', 0)) + self.block.count_sessions_new
        self.sequenced_block.total_contracts_new = int(parent_sequenced_block_data.get(
            'total_contracts_new', 0)) + self.block.count_contracts_new

        self.sequenced_block.session_id = int(
            parent_sequenced_block_data.get('session_id', 0))

        if parent_block_data and parent_block_data['count_sessions_new'] > 0:
            self.sequenced_block.session_id += 1


class AccountBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):
        self.block.count_accounts_new += len(set(self.block._accounts_new))
        self.block.count_accounts_reaped += len(
            set(self.block._accounts_reaped))

        self.block.count_accounts = self.block.count_accounts_new - \
            self.block.count_accounts_reaped

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for account_audit in AccountAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):
            try:
                account = Account.query(db_session).filter_by(
                    id=account_audit.account_id).one()

                if account_audit.type_id == ACCOUNT_AUDIT_TYPE_REAPED:
                    account.count_reaped += 1
                    account.is_reaped = True

                elif account_audit.type_id == ACCOUNT_AUDIT_TYPE_NEW:
                    account.is_reaped = False

                account.updated_at_block = self.block.id

            except NoResultFound:

                account = Account(
                    id=account_audit.account_id,
                    address=ss58_encode(
                        account_audit.account_id, SUBSTRATE_ADDRESS_TYPE),
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id,
                    balance=0
                )

                # If reaped but does not exist, create new account for now
                if account_audit.type_id != ACCOUNT_AUDIT_TYPE_NEW:
                    account.is_reaped = True
                    account.count_reaped = 1

            account.save(db_session)


class DemocracyProposalBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for proposal_audit in DemocracyProposalAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            if proposal_audit.type_id == DEMOCRACY_PROPOSAL_AUDIT_TYPE_PROPOSED:
                status = 'Proposed'
            elif proposal_audit.type_id == DEMOCRACY_PROPOSAL_AUDIT_TYPE_TABLED:
                status = 'Tabled'
            else:
                status = '[unknown]'

            try:
                proposal = DemocracyProposal.query(db_session).filter_by(
                    id=proposal_audit.democracy_proposal_id).one()

                proposal.status = status
                proposal.updated_at_block = self.block.id

            except NoResultFound:

                proposal = DemocracyProposal(
                    id=proposal_audit.democracy_proposal_id,
                    proposal=proposal_audit.data['proposal'],
                    bond=proposal_audit.data['bond'],
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id,
                    status=status
                )

            proposal.save(db_session)


class DemocracyReferendumBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        # TODO force insert on Started status
        for referendum_audit in DemocracyReferendumAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            success = None
            vote_threshold = None
            proposal = None

            if referendum_audit.type_id == DEMOCRACY_REFERENDUM_AUDIT_TYPE_STARTED:
                status = 'Started'
                vote_threshold = referendum_audit.data.get('vote_threshold')
                proposal = referendum_audit.data.get('proposal')

            elif referendum_audit.type_id == DEMOCRACY_REFERENDUM_AUDIT_TYPE_PASSED:
                status = 'Passed'
            elif referendum_audit.type_id == DEMOCRACY_REFERENDUM_AUDIT_TYPE_NOTPASSED:
                status = 'NotPassed'
            elif referendum_audit.type_id == DEMOCRACY_REFERENDUM_AUDIT_TYPE_CANCELLED:
                status = 'Cancelled'
            elif referendum_audit.type_id == DEMOCRACY_REFERENDUM_AUDIT_TYPE_EXECUTED:
                status = 'Executed'
                success = referendum_audit.data.get('success')
            else:
                status = '[unknown]'

            try:
                referendum = DemocracyReferendum.query(db_session).filter_by(
                    id=referendum_audit.democracy_referendum_id).one()

                if proposal:
                    referendum.proposal = proposal

                referendum.status = status
                referendum.updated_at_block = self.block.id
                referendum.success = success

            except NoResultFound:

                referendum = DemocracyReferendum(
                    id=referendum_audit.democracy_referendum_id,
                    vote_threshold=vote_threshold,
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id,
                    proposal=proposal,
                    success=success,
                    status=status
                )

            referendum.save(db_session)


class DemocracyVoteBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for vote_audit in DemocracyVoteAudit.query(db_session).filter_by(block_id=self.block.id).order_by('extrinsic_idx'):

            try:
                vote = DemocracyVote.query(db_session).filter_by(
                    democracy_referendum_id=vote_audit.democracy_referendum_id,
                    stash_account_id=vote_audit.data.get('stash_account_id')
                ).one()

                vote.updated_at_block = self.block.id

            except NoResultFound:

                vote = DemocracyVote(
                    democracy_referendum_id=vote_audit.democracy_referendum_id,
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id,
                    stash_account_id=vote_audit.data.get('stash_account_id')
                )

            vote.vote_account_id = vote_audit.data.get('vote_account_id')
            vote.vote_raw = vote_audit.data.get('vote_raw')
            vote.vote_yes = vote_audit.data.get('vote_yes')
            vote.vote_no = vote_audit.data.get('vote_no')
            vote.stash = vote_audit.data.get('stash')
            vote.conviction = vote_audit.data.get('conviction')
            vote.vote_yes_weighted = vote_audit.data.get('vote_yes_weighted')
            vote.vote_no_weighted = vote_audit.data.get('vote_no_weighted')

            vote.save(db_session)


class CouncilMotionBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for motion_audit in CouncilMotionAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            if motion_audit.type_id == COUNCIL_MOTION_TYPE_PROPOSED:
                motion = CouncilMotion(
                    motion_hash=motion_audit.motion_hash,
                    account_id=motion_audit.data.get(
                        'proposedBy').replace('0x', ''),
                    proposal=motion_audit.data.get('proposal'),
                    proposal_hash=motion_audit.data.get('proposalHash'),
                    member_threshold=motion_audit.data.get('threshold'),
                    proposal_id=motion_audit.data.get('proposalIndex'),
                    yes_votes_count=0,
                    no_votes_count=0,
                    status='Proposed',
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id
                )

                motion.save(db_session)
            else:

                motion = CouncilMotion.query(db_session).filter(
                    CouncilMotion.motion_hash == motion_audit.motion_hash,
                    CouncilMotion.status != 'Disapproved',
                    CouncilMotion.status != 'Executed',
                ).first()

                # Check if motion exists (otherwise motion is created in event that is not yet processed)
                if motion:
                    motion.updated_at_block = self.block.id

                    if motion_audit.type_id == COUNCIL_MOTION_TYPE_APPROVED:
                        motion.approved = motion_audit.data.get('approved')
                        motion.status = 'Approved'
                    elif motion_audit.type_id == COUNCIL_MOTION_TYPE_DISAPPROVED:
                        motion.approved = motion_audit.data.get('approved')
                        motion.status = 'Disapproved'
                    elif motion_audit.type_id == COUNCIL_MOTION_TYPE_EXECUTED:
                        motion.executed = motion_audit.data.get('executed')
                        motion.status = 'Executed'
                    else:
                        motion.status = '[unknown]'

                    motion.save(db_session)


class CouncilVoteBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for vote_audit in CouncilVoteAudit.query(db_session).filter_by(block_id=self.block.id).order_by('extrinsic_idx'):

            motion = CouncilMotion.query(db_session).filter(
                CouncilMotion.motion_hash == vote_audit.motion_hash,
                CouncilMotion.status != 'Disapproved',
                CouncilMotion.status != 'Executed',
            ).first()

            if motion:

                try:
                    vote = CouncilVote.query(db_session).filter_by(
                        proposal_id=motion.proposal_id,
                        account_id=vote_audit.data.get(
                            'account_id').replace('0x', ''),
                    ).one()

                    vote.updated_at_block = self.block.id

                except NoResultFound:

                    vote = CouncilVote(
                        proposal_id=motion.proposal_id,
                        motion_hash=vote_audit.motion_hash,
                        created_at_block=self.block.id,
                        updated_at_block=self.block.id,
                        account_id=vote_audit.data.get(
                            'account_id').replace('0x', ''),
                    )

                vote.vote = vote_audit.data.get('vote')

                # Update total vote count on motion

                motion.yes_votes_count = vote_audit.data.get('yes_votes_count')
                motion.no_votes_count = vote_audit.data.get('no_votes_count')

                motion.save(db_session)

                vote.save(db_session)


class TechCommProposalBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for motion_audit in TechCommProposalAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            if motion_audit.type_id == TECHCOMM_PROPOSAL_TYPE_PROPOSED:
                motion = TechCommProposal(
                    motion_hash=motion_audit.motion_hash,
                    account_id=motion_audit.data.get(
                        'proposedBy').replace('0x', ''),
                    proposal=motion_audit.data.get('proposal'),
                    proposal_hash=motion_audit.data.get('proposalHash'),
                    member_threshold=motion_audit.data.get('threshold'),
                    proposal_id=motion_audit.data.get('proposalIndex'),
                    yes_votes_count=0,
                    no_votes_count=0,
                    status='Proposed',
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id
                )

                motion.save(db_session)
            else:

                motion = TechCommProposal.query(db_session).filter(
                    TechCommProposal.motion_hash == motion_audit.motion_hash,
                    TechCommProposal.status != 'Disapproved',
                    TechCommProposal.status != 'Executed',
                ).first()

                # Check if motion exists (otherwise motion is created in event that is not yet processed)
                if motion:
                    motion.updated_at_block = self.block.id

                    if motion_audit.type_id == TECHCOMM_PROPOSAL_TYPE_APPROVED:
                        motion.approved = motion_audit.data.get('approved')
                        motion.status = 'Approved'
                    elif motion_audit.type_id == TECHCOMM_PROPOSAL_TYPE_DISAPPROVED:
                        motion.approved = motion_audit.data.get('approved')
                        motion.status = 'Disapproved'
                    elif motion_audit.type_id == TECHCOMM_PROPOSAL_TYPE_EXECUTED:
                        motion.executed = motion_audit.data.get('executed')
                        motion.status = 'Executed'
                    else:
                        motion.status = '[unknown]'

                    motion.save(db_session)


class TechCommProposalVoteBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for vote_audit in TechCommProposalVoteAudit.query(db_session).filter_by(block_id=self.block.id).order_by('extrinsic_idx'):

            motion = TechCommProposal.query(db_session).filter(
                TechCommProposal.motion_hash == vote_audit.motion_hash,
                TechCommProposal.status != 'Disapproved',
                TechCommProposal.status != 'Executed',
            ).first()

            if motion:

                try:
                    vote = TechCommProposalVote.query(db_session).filter_by(
                        proposal_id=motion.proposal_id,
                        account_id=vote_audit.data.get(
                            'account_id').replace('0x', ''),
                    ).one()

                    vote.updated_at_block = self.block.id

                except NoResultFound:

                    vote = TechCommProposalVote(
                        proposal_id=motion.proposal_id,
                        motion_hash=vote_audit.motion_hash,
                        created_at_block=self.block.id,
                        updated_at_block=self.block.id,
                        account_id=vote_audit.data.get(
                            'account_id').replace('0x', ''),
                    )

                vote.vote = vote_audit.data.get('vote')

                # Update total vote count on motion

                motion.yes_votes_count = vote_audit.data.get('yes_votes_count')
                motion.no_votes_count = vote_audit.data.get('no_votes_count')

                motion.save(db_session)

                vote.save(db_session)


class TreasuryProposalBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for proposal_audit in TreasuryProposalAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):

            if proposal_audit.type_id == TREASURY_PROPOSAL_TYPE_PROPOSED:
                proposal = TreasuryProposal(
                    proposal_id=proposal_audit.proposal_id,
                    proposed_by_account_id=proposal_audit.data.get(
                        'proposedBy').replace('0x', ''),
                    beneficiary_account_id=proposal_audit.data.get(
                        'beneficiary').replace('0x', ''),
                    value=proposal_audit.data.get('value'),
                    status='Proposed',
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id
                )

                proposal.save(db_session)
            else:

                proposal = TreasuryProposal.query(db_session).filter(
                    TreasuryProposal.proposal_id == proposal_audit.proposal_id,
                    TreasuryProposal.status != 'Awarded',
                    TreasuryProposal.status != 'Rejected',
                ).first()

                # Check if proposal exists (otherwise motion is created in event that is not yet processed)
                if proposal:
                    proposal.updated_at_block = self.block.id

                    if proposal_audit.type_id == TREASURY_PROPOSAL_TYPE_AWARDED:
                        proposal.status = 'Awarded'
                    elif proposal_audit.type_id == TREASURY_PROPOSAL_TYPE_REJECTED:
                        proposal.status = 'Rejected'
                        proposal.slash_value = proposal_audit.data.get(
                            'slash_value')
                    else:
                        proposal.status = '[unknown]'

                    proposal.save(db_session)


class AccountIndexBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for account_index_audit in AccountIndexAudit.query(db_session).filter_by(
                block_id=self.block.id
        ).order_by('event_idx'):

            if account_index_audit.type_id == ACCOUNT_INDEX_AUDIT_TYPE_NEW:

                # Check if account index already exists
                account_index = AccountIndex.query(db_session).filter_by(
                    id=account_index_audit.account_index_id
                ).first()

                if not account_index:

                    account_index = AccountIndex(
                        id=account_index_audit.account_index_id,
                        created_at_block=self.block.id
                    )

                account_index.account_id = account_index_audit.account_id
                account_index.short_address = ss58_encode_account_index(
                    account_index_audit.account_index_id,
                    SUBSTRATE_ADDRESS_TYPE
                )
                account_index.updated_at_block = self.block.id

                account_index.save(db_session)

            elif account_index_audit.type_id == ACCOUNT_INDEX_AUDIT_TYPE_REAPED:

                for account_index in AccountIndex.query(db_session).filter_by(
                        account_id=account_index_audit.account_id
                ):

                    account_index.account_id = None
                    account_index.is_reclaimable = True
                    account_index.updated_at_block = self.block.id


class MarketHistory1mBlockProcessor(BlockProcessor):
    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        current_block_time = self.block.datetime.replace(
            second=0, microsecond=0)
        latest_time = current_block_time - datetime.timedelta(minutes=1)

        current_base_quote_history = db_session.query(MarketHistory_1m.base, MarketHistory_1m.quote, func.max(MarketHistory_1m.time).label("time")).filter(
            MarketHistory_1m.time == current_block_time).group_by(MarketHistory_1m.base, MarketHistory_1m.quote).all()
        lastest_base_quote_history = db_session.query(MarketHistory_1m.base, MarketHistory_1m.quote, func.max(MarketHistory_1m.time).label("time")).filter(
            MarketHistory_1m.time == latest_time).group_by(MarketHistory_1m.base, MarketHistory_1m.quote).all()

        # curent -> next 1m all trades
        from_time = current_block_time
        to_time = from_time + \
            datetime.timedelta(minutes=1)
        block_scope = db_session.query(func.min(Block.id).label("from_id"), func.max(Block.id).label(
        "to_id")).filter(Block.datetime >= from_time, Block.datetime < to_time).order_by(Block.id).one()
        trades_result = db_session.query(Trade.base, Trade.quote, func.sum(Trade.base_amount).label("base_amount"), func.sum(Trade.quote_amount).label("quote_amount"), func.min(Trade.price).label("low"), func.max(Trade.price).label("high")).filter(Trade.block_id >= block_scope.from_id, Trade.block_id <= block_scope.to_id).group_by(Trade.base, Trade.quote).all()


        for trades in trades_result:
            open_result = db_session.query(Trade.price).filter(
                Trade.block_id >= block_scope.from_id, Trade.block_id <= block_scope.to_id, Trade.base == trades.base, Trade.quote == trades.quote).order_by(Trade.block_id.asc(), Trade.event_idx.asc()).limit(1).one()

            closed_result = db_session.query(Trade.price).filter(
                Trade.block_id >= block_scope.from_id, Trade.block_id <= block_scope.to_id, Trade.base==trades.base, Trade.quote==trades.quote).order_by(Trade.block_id.desc(), Trade.event_idx.desc()).limit(1).one()

            matched = False
            for current_base_quote in current_base_quote_history:
                if trades.base == current_base_quote.base and trades.quote == current_base_quote.quote:
                    matched = True
                    break

            if matched:  # update last market record
                record = MarketHistory_1m.query(
                        db_session).filter_by(base=trades.base, quote=trades.quote, time=current_block_time).first()
                record.open = open_result[0]
                record.high = trades.high
                record.low = trades.low
                record.close = closed_result[0]
                record.base_amount = trades.base_amount
                record.quote_amount = trades.quote_amount
                record.save(db_session)
            else:
                model = MarketHistory_1m(
                    time=from_time,
                    open=open_result[0],
                    high=trades.high,
                    low=trades.low,
                    close=closed_result[0],
                    base_amount=trades.base_amount,
                    quote_amount=trades.quote_amount,
                    base=trades.base,
                    quote=trades.quote
                )

                model.save(db_session)

        # prev record exist, but not exist current block, will record empty in current scope
        for latest_base_quote in lastest_base_quote_history:
            matched = False

            for trades in trades_result: # not exist current block
                if latest_base_quote.base == trades.base and latest_base_quote.quote == trades.quote:
                    matched = True
                    break
            for base_quote_history in current_base_quote_history: # not exist current record
                if latest_base_quote.base == base_quote_history.base and latest_base_quote.quote == base_quote_history.quote:
                    matched = True
                    break

            if not matched:
                record = MarketHistory_1m.query(
                    db_session).filter_by(base=latest_base_quote.base, quote=latest_base_quote.quote, time=latest_base_quote.time).first()
                model = MarketHistory_1m(
                    time=from_time,
                    open=record.close,
                    high=record.close,
                    low=record.close,
                    close=record.close,
                    base_amount=0,
                    quote_amount=0,
                    base=latest_base_quote.base,
                    quote=latest_base_quote.quote
                )

                model.save(db_session)

class MarketHistory5mBlockProcessor(BlockProcessor):
    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        current_block_time = self.block.datetime.replace(minute=self.block.datetime.minute - (self.block.datetime.minute % 5),
            second=0, microsecond=0)
        latest_time = current_block_time - datetime.timedelta(minutes=5)

        current_base_quote_history = db_session.query(MarketHistory_5m.base, MarketHistory_5m.quote, func.max(MarketHistory_5m.time).label("time")).filter(
            MarketHistory_5m.time == current_block_time).group_by(MarketHistory_5m.base, MarketHistory_5m.quote).all()
        lastest_base_quote_history = db_session.query(MarketHistory_5m.base, MarketHistory_5m.quote, func.max(MarketHistory_5m.time).label("time")).filter(
            MarketHistory_5m.time == latest_time).group_by(MarketHistory_5m.base, MarketHistory_5m.quote).all()

        # curent -> next 5m all trades
        from_time = current_block_time
        to_time = from_time + \
            datetime.timedelta(minutes=5)
        trades_result = db_session.query(MarketHistory_1m.base, MarketHistory_1m.quote, func.sum(MarketHistory_1m.base_amount).label("base_amount"), func.sum(MarketHistory_1m.quote_amount).label("quote_amount"), func.min(
            MarketHistory_1m.low).label("low"), func.max(MarketHistory_1m.high).label("high")).filter(MarketHistory_1m.time >= from_time, MarketHistory_1m.time < to_time).group_by(MarketHistory_1m.base, MarketHistory_1m.quote).all()

        for trades in trades_result:
            open_result = db_session.query(MarketHistory_1m.open).filter(
                MarketHistory_1m.base == trades.base, MarketHistory_1m.quote == trades.quote, MarketHistory_1m.time >= from_time, MarketHistory_1m.time < to_time).order_by(MarketHistory_1m.id.asc()).limit(1).one()

            closed_result = db_session.query(MarketHistory_1m.close).filter(
                MarketHistory_1m.base == trades.base, MarketHistory_1m.quote == trades.quote, MarketHistory_1m.time >= from_time, MarketHistory_1m.time < to_time).order_by(MarketHistory_1m.id.desc()).limit(1).one()

            matched = False
            for current_base_quote in current_base_quote_history:
                if trades.base == current_base_quote.base and trades.quote == current_base_quote.quote:
                    matched = True
                    break

            if matched:  # update last market record
                record = MarketHistory_5m.query(
                        db_session).filter_by(base=trades.base, quote=trades.quote, time=current_block_time).first()
                record.open = open_result[0]
                record.high = trades.high
                record.low = trades.low
                record.close = closed_result[0]
                record.base_amount = trades.base_amount
                record.quote_amount = trades.quote_amount
                record.save(db_session)
            else:
                model = MarketHistory_5m(
                    time=from_time,
                    open=open_result[0],
                    high=trades.high,
                    low=trades.low,
                    close=closed_result[0],
                    base_amount=trades.base_amount,
                    quote_amount=trades.quote_amount,
                    base=trades.base,
                    quote=trades.quote
                )

                model.save(db_session)

        # prev record exist, but not exist current block, will record empty in current scope
        for latest_base_quote in lastest_base_quote_history:
            matched = False
            for trades in trades_result:
                if latest_base_quote.base == trades.base and latest_base_quote.quote == trades.quote:
                    matched = True
                    break
            for base_quote_history in current_base_quote_history: # not exist current record
                if latest_base_quote.base == base_quote_history.base and latest_base_quote.quote == base_quote_history.quote:
                    matched = True
                    break

            if not matched:
                record = MarketHistory_5m.query(
                    db_session).filter_by(base=latest_base_quote.base, quote=latest_base_quote.quote, time=latest_base_quote.time).first()
                model = MarketHistory_5m(
                    time=from_time,
                    open=record.close,
                    high=record.close,
                    low=record.close,
                    close=record.close,
                    base_amount=0,
                    quote_amount=0,
                    base=latest_base_quote.base,
                    quote=latest_base_quote.quote
                )

                model.save(db_session)


class MarketHistory1hBlockProcessor(BlockProcessor):
    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        current_block_time = self.block.datetime.replace(minute=0,
                                                         second=0, microsecond=0)
        latest_time = current_block_time - datetime.timedelta(hours=1)

        current_base_quote_history = db_session.query(MarketHistory_1h.base, MarketHistory_1h.quote, func.max(MarketHistory_1h.time).label("time")).filter(
            MarketHistory_1h.time == current_block_time).group_by(MarketHistory_1h.base, MarketHistory_1h.quote).all()
        lastest_base_quote_history = db_session.query(MarketHistory_1h.base, MarketHistory_1h.quote, func.max(MarketHistory_1h.time).label("time")).filter(
            MarketHistory_1h.time == latest_time).group_by(MarketHistory_1h.base, MarketHistory_1h.quote).all()

        # curent -> next 1h all trades
        from_time = current_block_time
        to_time = from_time + \
            datetime.timedelta(hours=1)
        trades_result = db_session.query(MarketHistory_5m.base, MarketHistory_5m.quote, func.sum(MarketHistory_5m.base_amount).label("base_amount"), func.sum(MarketHistory_5m.quote_amount).label("quote_amount"), func.min(
            MarketHistory_5m.low).label("low"), func.max(MarketHistory_5m.high).label("high")).filter(MarketHistory_5m.time >= from_time, MarketHistory_5m.time < to_time).group_by(MarketHistory_5m.base, MarketHistory_5m.quote).all()

        for trades in trades_result:
            open_result = db_session.query(MarketHistory_5m.open).filter(
                MarketHistory_5m.base == trades.base, MarketHistory_5m.quote == trades.quote, MarketHistory_5m.time >= from_time, MarketHistory_5m.time < to_time).order_by(MarketHistory_5m.id.asc()).limit(1).one()

            closed_result = db_session.query(MarketHistory_5m.close).filter(
                MarketHistory_5m.base == trades.base, MarketHistory_5m.quote == trades.quote, MarketHistory_5m.time >= from_time, MarketHistory_5m.time < to_time).order_by(MarketHistory_5m.id.desc()).limit(1).one()

            matched = False
            for current_base_quote in current_base_quote_history:
                if trades.base == current_base_quote.base and trades.quote == current_base_quote.quote:
                    matched = True
                    break

            if matched:  # update last market record
                record = MarketHistory_1h.query(
                    db_session).filter_by(base=trades.base, quote=trades.quote, time=current_block_time).first()
                record.open = open_result[0]
                record.high = trades.high
                record.low = trades.low
                record.close = closed_result[0]
                record.base_amount = trades.base_amount
                record.quote_amount = trades.quote_amount
                record.save(db_session)
            else:
                model = MarketHistory_1h(
                    time=from_time,
                    open=open_result[0],
                    high=trades.high,
                    low=trades.low,
                    close=closed_result[0],
                    base_amount=trades.base_amount,
                    quote_amount=trades.quote_amount,
                    base=trades.base,
                    quote=trades.quote
                )

                model.save(db_session)

        # prev record exist, but not exist current block, will record empty in current scope
        for latest_base_quote in lastest_base_quote_history:
            matched = False
            for trades in trades_result:
                if latest_base_quote.base == trades.base and latest_base_quote.quote == trades.quote:
                    matched = True
                    break
            for base_quote_history in current_base_quote_history:  # not exist current record
                if latest_base_quote.base == base_quote_history.base and latest_base_quote.quote == base_quote_history.quote:
                    matched = True
                    break

            if not matched:
                record = MarketHistory_1h.query(
                    db_session).filter_by(base=latest_base_quote.base, quote=latest_base_quote.quote, time=latest_base_quote.time).first()
                model = MarketHistory_1h(
                    time=from_time,
                    open=record.close,
                    high=record.close,
                    low=record.close,
                    close=record.close,
                    base_amount=0,
                    quote_amount=0,
                    base=latest_base_quote.base,
                    quote=latest_base_quote.quote
                )

                model.save(db_session)


class MarketHistory1dBlockProcessor(BlockProcessor):
    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        current_block_time = self.block.datetime.replace(hour=0,minute=0,
                                                         second=0, microsecond=0)
        latest_time = current_block_time - datetime.timedelta(days=1)

        current_base_quote_history = db_session.query(MarketHistory_1d.base, MarketHistory_1d.quote, func.max(MarketHistory_1d.time).label("time")).filter(
            MarketHistory_1d.time == current_block_time).group_by(MarketHistory_1d.base, MarketHistory_1d.quote).all()
        lastest_base_quote_history = db_session.query(MarketHistory_1d.base, MarketHistory_1d.quote, func.max(MarketHistory_1d.time).label("time")).filter(
            MarketHistory_1d.time == latest_time).group_by(MarketHistory_1d.base, MarketHistory_1d.quote).all()

        # curent -> next 5m all trades
        from_time = current_block_time
        to_time = from_time + \
            datetime.timedelta(days=1)
        trades_result = db_session.query(MarketHistory_1h.base, MarketHistory_1h.quote, func.sum(MarketHistory_1h.base_amount).label("base_amount"), func.sum(MarketHistory_1h.quote_amount).label("quote_amount"), func.min(
            MarketHistory_1h.low).label("low"), func.max(MarketHistory_1h.high).label("high")).filter(MarketHistory_1h.time >= from_time, MarketHistory_1h.time < to_time).group_by(MarketHistory_1h.base, MarketHistory_1h.quote).all()

        for trades in trades_result:
            open_result = db_session.query(MarketHistory_1h.open).filter(
                MarketHistory_1h.base == trades.base, MarketHistory_1h.quote == trades.quote, MarketHistory_1h.time >= from_time, MarketHistory_1h.time < to_time).order_by(MarketHistory_1h.id.asc()).limit(1).one()

            closed_result = db_session.query(MarketHistory_1h.close).filter(
                MarketHistory_1h.base == trades.base, MarketHistory_1h.quote == trades.quote, MarketHistory_1h.time >= from_time, MarketHistory_1h.time < to_time).order_by(MarketHistory_1h.id.desc()).limit(1).one()

            matched = False
            for current_base_quote in current_base_quote_history:
                if trades.base == current_base_quote.base and trades.quote == current_base_quote.quote:
                    matched = True
                    break

            if matched:  # update last market record
                record = MarketHistory_1d.query(
                    db_session).filter_by(base=trades.base, quote=trades.quote, time=current_block_time).first()
                record.open = open_result[0]
                record.high = trades.high
                record.low = trades.low
                record.close = closed_result[0]
                record.base_amount = trades.base_amount
                record.quote_amount = trades.quote_amount
                record.save(db_session)
            else:
                model = MarketHistory_1d(
                    time=from_time,
                    open=open_result[0],
                    high=trades.high,
                    low=trades.low,
                    close=closed_result[0],
                    base_amount=trades.base_amount,
                    quote_amount=trades.quote_amount,
                    base=trades.base,
                    quote=trades.quote
                )

                model.save(db_session)

        # prev record exist, but not exist current block, will record empty in current scope
        for latest_base_quote in lastest_base_quote_history:
            matched = False
            for trades in trades_result:
                if latest_base_quote.base == trades.base and latest_base_quote.quote == trades.quote:
                    matched = True
                    break
            for base_quote_history in current_base_quote_history:  # not exist current record
                if latest_base_quote.base == base_quote_history.base and latest_base_quote.quote == base_quote_history.quote:
                    matched = True
                    break

            if not matched:
                record = MarketHistory_1d.query(
                    db_session).filter_by(base=latest_base_quote.base, quote=latest_base_quote.quote, time=latest_base_quote.time).first()
                model = MarketHistory_1d(
                    time=from_time,
                    open=record.close,
                    high=record.close,
                    low=record.close,
                    close=record.close,
                    base_amount=0,
                    quote_amount=0,
                    base=latest_base_quote.base,
                    quote=latest_base_quote.quote
                )

                model.save(db_session)
