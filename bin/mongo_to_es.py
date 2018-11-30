# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from builtins import open
from builtins import input
from builtins import int
from builtins import str
from future import standard_library
standard_library.install_aliases()
import os
import sys
import json
import click
import requests
import pymongo
from elasticsearch import Elasticsearch
from elasticsearch import helpers
from pprint import pprint
from datetime import datetime, timedelta
from distutils.util import strtobool

try:
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'gazouilloire', 'database', 'db_mappings.json'), 'r') as db_mappings:
        DB_MAPPINGS = json.loads(db_mappings.read())
except FileNotFoundError as e:
    print('ERROR -', 'Could not open db_mappings.json: %s %s' % (type(e), e))
    sys.exit(1)

pymongo.unicode_decode_output = False

ES_TWEETS_MAPPINGS = DB_MAPPINGS['tweets_mapping']
ES_LINKS_MAPPINGS = DB_MAPPINGS['links_mapping']


@click.command()
@click.argument('mongo_host')
@click.argument('mongo_port')
@click.argument('mongo_db')
@click.argument('es_host')
@click.argument('es_port')
@click.argument('es_index_name')
def migrate(mongo_host, mongo_port, mongo_db, es_host, es_port, es_index_name):
    print("Initialising Mongo & ES clients...")
    MONGO_CLIENT = pymongo.MongoClient(
        'mongodb://' + mongo_host + ':' + mongo_port + '/')
    MONGO_DB = MONGO_CLIENT[mongo_db]
    ES_CLIENT = Elasticsearch('http://' + es_host + ':' + es_port)
    ES_INDEX_NAME = es_index_name
    ES_LINKS_INDEX = ES_INDEX_NAME + '_links'
    ES_TWEETS_INDEX = ES_INDEX_NAME + '_tweets'

    if not ES_CLIENT.indices.exists(index=ES_TWEETS_INDEX):
        ES_CLIENT.indices.create(
            index=ES_TWEETS_INDEX, body=ES_TWEETS_MAPPINGS)
        existing_indices = []
    else:
        existing_indices = [ES_TWEETS_INDEX]

    if not ES_CLIENT.indices.exists(index=ES_LINKS_INDEX):
        ES_CLIENT.indices.create(
            index=ES_LINKS_INDEX, body=ES_LINKS_MAPPINGS)
    else:
        existing_indices.append(ES_LINKS_INDEX)
    if len(existing_indices) == 2:
        choice = strtobool(input(
            "WARNING: ES indices " + existing_indices[0] + " & " + existing_indices[1] + " already exist. Are you sure that you want to add tweets in these indices?\n(y/n) "))
        if not choice:
            sys.exit()
    elif len(existing_indices) == 1:
        choice = strtobool(input(
            "WARNING: ES index " + existing_indices[0] + " already exists. Are you sure that you want to add tweets in this index?\n(y/n) "))
        if not choice:
            sys.exit()
    startTime = datetime.now()
    i = 0
    bulkload = []
    print("Migrating database...")
    for tweet in MONGO_DB.tweets.find():
        i += 1
        try:
            user_created_at_timestamp = tweet['user_created_at_timestamp']
        except:
            user_created_at_timestamp = None
        try:
            possibly_sensitive = tweet['possibly_sensitive']
        except:
            possibly_sensitive = None
        try:
            reply_count = tweet['reply_count']
        except:
            reply_count = None
        try:
            coordinates = tweet['coordinates']['coordinates']
        except:
            coordinates = tweet.get('coordinates', None)
        try:
            proper_links = tweet['proper_links']
        except:
            proper_links = None
        load = {
            '_id': tweet['_id'],
            '_source': {
                "collected_at_timestamp": tweet['collected_at_timestamp'],
                "collected_via_search": tweet.get('collected_via_search', None),
                "collected_via_stream": tweet.get('collected_via_stream', None),
                "coordinates": coordinates,
                "created_at": tweet['created_at'],
                "deleted": False,
                "favorite_count": tweet['favorite_count'],
                "hashtags": tweet['hashtags'],
                "in_reply_to_screen_name": tweet['in_reply_to_screen_name'],
                "in_reply_to_status_id_str": tweet['in_reply_to_status_id_str'],
                "in_reply_to_user_id_str": tweet['in_reply_to_user_id_str'],
                "lang": tweet['lang'],
                "langs": tweet['langs'],
                "links": tweet['links'],
                "links_to_resolve": tweet['links_to_resolve'],
                "medias": tweet['medias'],
                "mentions_ids": tweet['mentions_ids'],
                "mentions_names": tweet['mentions_names'],
                "possibly_sensitive": possibly_sensitive,
                "proper_links": proper_links,
                "quoted_id": tweet['quoted_id'],
                "quoted_timestamp": tweet['quoted_timestamp'],
                "quoted_user": tweet['quoted_user'],
                "quoted_user_id": tweet['quoted_user_id'],
                "reply_count": reply_count,
                "retweet_count": tweet['retweet_count'],
                "retweet_id": tweet['retweet_id'],
                "retweet_timestamp": tweet['retweet_timestamp'],
                "retweet_user": tweet['retweet_user'],
                "retweet_user_id": tweet['retweet_user_id'],
                "source": tweet['source'],
                "text": tweet['text'],
                "timestamp": int(tweet['timestamp']),
                "truncated": tweet['truncated'],
                "tweet_id": tweet['_id'],
                "url": tweet['url'],
                "user_created_at": tweet['user_created_at'],
                "user_created_at_timestamp": user_created_at_timestamp,
                "user_description": tweet['user_description'],
                "user_favourites": tweet['user_favourites'],
                "user_followers": tweet['user_followers'],
                "user_friends": tweet['user_friends'],
                "user_id_str": tweet['user_id_str'],
                "user_lang": tweet['user_lang'],
                "user_listed": tweet['user_listed'],
                "user_location": tweet['user_location'],
                "user_name": tweet['user_name'],
                "user_profile_image_url": tweet['user_profile_image_url'],
                "user_profile_image_url_https": tweet['user_profile_image_url_https'],
                "user_screen_name": tweet['user_screen_name'],
                "user_statuses": tweet['user_statuses'],
                "user_time_zone": tweet['user_time_zone'],
                "user_url": tweet['user_url'],
                "user_utc_offset": tweet['user_utc_offset'],
                "user_verified": tweet['user_verified']}}

        bulkload.append(load)

        if i % 1800 == 0:
            helpers.bulk(ES_CLIENT, bulkload,
                         index=ES_TWEETS_INDEX, doc_type='tweet')
            bulkload = []
            print('  ' + str(i) + " tweets indexed.", end="\r")
    helpers.bulk(ES_CLIENT, bulkload, index=ES_TWEETS_INDEX, doc_type='tweet')
    print('  ' + str(i) + " tweets indexed.")
    i = 0
    links_bulkload = []
    for link in MONGO_DB.links.find():
        i += 1

        try:
            real = link['real']
        except:
            real = None

        load = {
            '_source': {
                "link_id": link['_id'],
                "real": real
            }}

        links_bulkload.append(load)

        if i % 1800 == 0:
            helpers.bulk(ES_CLIENT, links_bulkload,
                         index=ES_LINKS_INDEX, doc_type='link')
            links_bulkload = []
            print('  ' + str(i) + " links indexed.", end="\r")
    helpers.bulk(ES_CLIENT, links_bulkload,
                 index=ES_LINKS_INDEX, doc_type='link')
    print('  ' + str(i) + " links indexed.")
    print('Done (took', str((datetime.now() - startTime).total_seconds()) + ' seconds)')


if __name__ == '__main__':
    migrate()
