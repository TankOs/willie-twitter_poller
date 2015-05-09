import willie
import rauth
import json
import os
import pprint

def create_hashtag_dict():
	return {
		"channels": [],
		"last_id": None,
	}

def setup( bot ):
	bot.twitter_db_filename = os.path.join(
		bot.config.dotdir,
		bot.nick + "-twitter.db",
	)

	bot.memory["twitter_data"] = {
		"ignored_users": [],
		"hashtags": {},
	}

	if os.path.exists( bot.twitter_db_filename ):
		fh = open( bot.twitter_db_filename, "r" )
		bot.memory["twitter_data"].update( json.load( fh ) )
		fh.close()

def save_data( bot ):
	fh = open( bot.twitter_db_filename, "w" )
	fh.write( json.dumps( bot.memory["twitter_data"] ) )
	fh.close()

def create_oauth_session( bot ):
	service = rauth.OAuth1Service(
		name = "twitter",
		consumer_key = bot.config.twitter.consumer_key,
		consumer_secret = bot.config.twitter.consumer_secret,
		base_url = "https://api.twitter.com/1.1/",
	)
	session = service.get_session(
		(
			bot.config.twitter.access_token_key,
			bot.config.twitter.access_token_secret
		)
	)
	return session

@willie.module.commands( "twitter:monitor" )
def monitor_command( bot, trigger ):
	if(
		trigger.admin is True and
		trigger.sender[0] == u"#"
	):
		hashtag = trigger.group( 3 )

		if len( hashtag ) < 2 or hashtag[0] != u"#":
			bot.reply( u"Invalid hashtag: {0}".format( hashtag ) )
		else:
			data = bot.memory["twitter_data"]

			options = data["hashtags"].get( hashtag ) or create_hashtag_dict()

			if trigger.sender not in options["channels"]:
				options["channels"].append( trigger.sender )

			data["hashtags"][hashtag] = options
			save_data( bot )

			bot.reply( u"Now monitoring {0}.".format( hashtag ) )
			poll_hashtags( bot )

@willie.module.interval( 60 )
def poll_hashtags( bot ):
	session = create_oauth_session( bot )
	twitter_data = bot.memory["twitter_data"]

	for hashtag, options in twitter_data["hashtags"].items():
		params = {
			"q": hashtag,
			"result_type": "recent",
		}

		if options["last_id"] is not None:
			params["since_id"] = options["last_id"]

		data = session.get( "search/tweets.json", params = params ).json()
		items = data["statuses"]

		# Filter out retweets.
		items = [
			item
			for item in items
			if(
				item["text"].startswith( "RT" ) is False and (
					"ignored_users" not in twitter_data or (
						item["user"]["screen_name"].lower() not in
						twitter_data["ignored_users"]
					)
				)
			)
		]

		highest_id = options["last_id"] or 0

		# Find highest ID of *all* tweets.
		for status in items:
			highest_id = max( highest_id, int( status["id"] ) )

		options["last_id"] = highest_id

		for channel in options["channels"]:
			tweet_number = 1

			for status in items[0:5]:
				banner = u"\x02\x032[TWITTER]\x030\x02"
				user = u"@{0}".format( status["user"]["screen_name"] )
				text = status["text"]
				irc_text = u"{2} \x032{3} \x033{0}\x03: {1} [{4}/{5}]".format(
					user,
					text,
					banner,
					hashtag,
					tweet_number,
					len( items ),
				)

				bot.msg( channel, irc_text )

				tweet_number += 1

			if len( items ) > 5:
				bot.msg( channel, u"(showing a maximum of 5 tweets)" )

	save_data( bot )

@willie.module.commands( "twitter:sync" )
def poll_now( bot, trigger ):
	if trigger.admin is True:
		bot.reply( u"Synchronizing now..." )
		poll_hashtags( bot )

@willie.module.commands( "twitter:list" )
def list_command( bot, trigger ):
	channel = trigger.sender
	data = bot.memory["twitter_data"]

	if channel[0] == "#":
		hashtags = []

		for hashtag, options in data["hashtags"].items():
			if channel in options["channels"]:
				hashtags.append( hashtag )

		if len( hashtags ) < 1:
			bot.reply( u"No hashtags are monitored for this channel." )
		else:
			bot.reply( u"Monitoring: {0}".format( u", ".join( hashtags ) ) )

@willie.module.commands( "twitter:unmonitor" )
def unmonitor_command( bot, trigger ):
	channel = trigger.sender
	data = bot.memory["twitter_data"]

	if(
		trigger.admin is True and
		channel[0] == u"#"
	):
		hashtag = trigger.group( 3 )

		if len( hashtag ) < 2 or hashtag[0] != u"#":
			bot.reply( u"Invalid hashtag: {0}".format( hashtag ) )
		else:
			hashtag_data = data["hashtags"].get( hashtag )

			if hashtag_data is None or channel not in hashtag_data["channels"]:
				bot.reply( u"{0} is not monitored.".format( hashtag ) )
			else:
				hashtag_data["channels"].remove( channel )

				if len( hashtag_data["channels"] ) < 1:
					del data["hashtags"][hashtag]

				save_data( bot )
				bot.reply( u"Stopped monitoring {0}.".format( hashtag ) )

@willie.module.commands( "twitter:ignore" )
def ignore_command( bot, trigger ):
	data = bot.memory["twitter_data"]

	if "ignored_users" not in data:
		data["ignored_users"] = []

	if trigger.admin is True:
		user = trigger.group( 3 ).lower()

		if user not in data["ignored_users"]:
			data["ignored_users"].append( user )

		bot.reply( u"Added {0} to ignore list.".format( trigger.group( 3 ) ) )

	save_data( bot )

@willie.module.commands( "twitter:unignore" )
def unignore_command( bot, trigger ):
	data = bot.memory["twitter_data"]

	if "ignored_users" in data and trigger.admin is True:
		user = trigger.group( 3 ).lower()

		if user in data["ignored_users"]:
			data["ignored_users"].remove( user )

		bot.reply( u"Removed {0} from ignore list.".format( trigger.group( 3 ) ) )

	save_data( bot )

@willie.module.commands( "twitter:ignorelist" )
def ignorelist_command( bot, trigger ):
	data = bot.memory["twitter_data"]

	if trigger.admin is True:
		bot.reply(
			u"Ignored users: {0}".format( u", ".join( data["ignored_users"] ) )
		)
