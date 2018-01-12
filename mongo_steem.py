from bson import json_util
from piston.steem import Steem
from piston.post import Post
from pymongo import MongoClient
from steembase.exceptions import PostDoesNotExist
import datetime
import json
import time

CRYPTO_NEWS = 'crypto-news'
WIF = '5KHfXHFuAWziwBZRfx1v6HbtLT5QbrtD5V5ZMYk26fDLmvxDAH6'
STEEMIT_WSS_NODES = [
    'wss://gtg.steem.house:8090',
    'wss://seed.bitcoiner.me',
]
JACKSON_KONTNY = 'jackson.kontny'

def convert_post_datetime(post_datetime_str):
    return datetime.datetime.strptime(
        post_datetime_str, "%Y-%m-%dT%H:%M:%S.000Z")

def datetime_filter(start_time, end_time=None):
    if not end_time:
        end_time = datetime.datetime.now()
    end_time = end_time + datetime.timedelta(hours=6)
    start_time = start_time + datetime.timedelta(hours=6)
    return {"created": {"$gte": start_time, "$lte": end_time}}

def vote_count_filter(vote_count):
    return {"$where": "this.active_votes.length > {}".format(vote_count)}

class MongoSteem(object):

    def __init__(self, steem, host_name='mongodb://localhost/test', db_name='test'):
        self.steem = steem
        mongo_client = MongoClient(host_name)
        self.db = getattr(mongo_client, db_name)

    def stream_fresh_posts(self, is_main=True, allow_votes=True, expiration_minutes=15):
        """
        Retrieves posts filtered by the input criteria.

        * Args
            * is_main -> boolean that designates if comments should be filtered out
            * allow_votes -> boolean that designates if posts that do not allow
                votes should be filtered out
            * expiration_minutes -> integer defining how old a post can be before
                filtering it out

        """
        for post in self.steem.stream_comments():
            try:
                if (
                        (not is_main or post.is_main_post()) and
                        (not allow_votes or post.allow_votes) and
                        post.time_elapsed() < datetime.timedelta(
                            minutes=expiration_minutes)
                ):
                    yield post
            except PostDoesNotExist:
                pass
            except Exception as e:
                print(e)

    def stream_to_mongo(self):
        try:
            for fresh_post in self.stream_fresh_posts():
                post_data = fresh_post.__dict__
                del post_data['steem']
                self.db.posts.insert_one(post_data)
                print('successfully inserted')

        except Exception as e:
            print(e)

    def stream_posts_from_mongo(self, query=None, limit=None):
        if query is None:
            query = {}
        post_query = self.db.posts.find(query)
        if limit:
            post_query = post_query.limit(limit)
        try:
            for post_data in post_query:
                yield Post(post_data['identifier'], steem_instance=self.steem)

        except Exception as e:
            print(e)

    def update_posts(self, query=None):
        if not query:
            query = {}
        for post in self.stream_posts_from_mongo(query=query):
            post_data = post.__dict__
            del post_data['steem']
            self.db.posts.update_one(
                {'identifier': post.identifier}, {'$set': post_data})


class PostMiner(object):

    def __init__(self, mongo_steem, category=CRYPTO_NEWS, expiration_minutes=60, sleep_time=60):
        self.mongo_steem = mongo_steem
        self.category = category
        self.expiration_minutes = expiration_minutes
        self.sleep_time = sleep_time
        self.detected_winners = []

    def mine_winners(self):
        while True:
            winning_post_query = self.get_target_query()
            winning_post_query.update(vote_count_filter(3))
            winning_post_query.update({"identifier": {"$nin": self.detected_winners}})
            winner_query = self.mongo_steem.db.posts.find(
                winning_post_query, {"identifier": 1}
            )
            winners = [winner['identifier'] for winner in winner_query]
            self.detected_winners.extend(winners)
            yield winners

            time.sleep(self.sleep_time)
            self.update_target_posts()

    def update_target_posts(self):
        update_post_query = self.get_target_query()
        self.mongo_steem.update_posts(query=update_post_query)

    def get_target_query(self):
        target_query = {"category": self.category}
        target_query.update(datetime_filter(
            start_time=datetime.datetime.now() - datetime.timedelta(minutes=self.expiration_minutes)
        ))
        return target_query


class SteemVoter(object):

    def __init__(self, steem, voter=JACKSON_KONTNY):
        self.steem = steem
        self.voter = voter

    def upvote_winner(self, winner):
        winning_post = Post(winner, steem_instance=self.steem)
        winning_post.upvote(voter=self.voter)
        self.upvoted_winners.append(winner)
        print('winning post: {}'.format(winner))

        # cannot post two consecutive votes less than 3 seconds apart
        time.sleep(3)


class SteemCurator(object):

    def __init__(self, steem=None, post_miner=None, steem_voter=None, vote_limit=11, run_hours=24):
        if steem is None:
            steem = Steem(node=STEEMIT_WSS_NODES, wif=WIF)
        if mongo_steem is None:
            mongo_steem = MongoSteem(steem=steem)
        if not post_miner:
            post_miner = PostMiner(mongo_steem=mongo_steem)
        if not steem_voter:
            steem_voter = SteemVoter(steem=steem)
        self.post_miner = post_miner
        self.steem_voter = steem_voter
        self.vote_limit = vote_limit
        self.end_time = datetime.datetime.now() + datetime.timedelta(hours=run_hours)

    def run(self):
        while not self.post_quota_met:
            for winner_group in self.post_miner.mine_winners():
                for winner in winner_group:
                    self.steem_voter.upvote_winner(winner)

    @property
    def post_quota_met(self):
        return len(self.upvoted_winners) >= self.vote_limit or datetime.datetime.now() > self.end_time
