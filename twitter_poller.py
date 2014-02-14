import willie
import rauth
import json
import os

def setup( bot ):
	bot.twitter_db_filename = os.path.join(
		bot.config.dotdir,
		bot.nick + "-twitter.db",
	)

	bot.memory["twitter_data"] = {}

	if os.path.exists( bot.twitter_db_filename ):
		fh = open( bot.twitter_db_filename, "r" )
		bot.memory["twitter_data"] = json.load( fh )
		fh.close()

def save_data( bot ):
	fh = open( bot.twitter_db_filename, "w" )
	fh.write( json.dumps( bot.memory["twitter_data"] ) )
	fh.close()

def create_options_dict():
	return {
		"channels": [],
		"last_id": None,
	}

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

			options = data.get( hashtag ) or create_options_dict()

			if trigger.sender not in options["channels"]:
				options["channels"].append( trigger.sender )

			data[hashtag] = options

			save_data( bot )

			bot.reply( u"Now monitoring {0}.".format( hashtag ) )
			poll_hashtags( bot )

@willie.module.interval( 60 )
def poll_hashtags( bot ):
	session = create_oauth_session( bot )
	twitter_data = bot.memory["twitter_data"]

	for hashtag, options in twitter_data.items():
		params = {
			"q": hashtag,
			"result_type": "recent",
		}

		if options["last_id"] is not None:
			params["since_id"] = options["last_id"]

		data = session.get( "search/tweets.json", params = params ).json()
		items = data["statuses"]

		highest_id = options["last_id"] or 0

		# Find highest ID of *all* tweets.
		for status in items:
			highest_id = max( highest_id, int( status["id"] ) )

		options["last_id"] = highest_id

		for channel in options["channels"]:
			for status in items[0:5]:
				banner = u"\x02\x032[TWITTER]\x030\x02"
				user = u"@{0}".format( status["user"]["screen_name"] )
				text = status["text"]
				irc_text = u"{2} \x032{3} \x033{0}\x030: {1}".format(
					user,
					text,
					banner,
					hashtag,
				)

				bot.msg( channel, irc_text )

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

		for hashtag, options in data.items():
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
			hashtag_data = data[hashtag] if hashtag in data else None

			if hashtag_data is None or channel not in hashtag_data["channels"]:
				bot.reply( u"{0} is not monitored.".format( hashtag ) )
			else:
				hashtag_data["channels"].remove( channel )

				if len( hashtag_data["channels"] ) < 1:
					del data[hashtag]

				save_data( bot )
				bot.reply( u"Stopped monitoring {0}.".format( hashtag ) )

