import praw
import signal
from fuzzywuzzy import fuzz
from slack_python_logging import slack_logger
from time import sleep

class PastaKiller(object):
    __slots__ = ["subreddit", "ignored_strings", "old_comments", "minimum_length",
                 "match_threshold", "logger"]

    def __init__(self, reddit, subreddit, minimum_length = 10,
                 match_threshold = 75, ignored_strings = []):
        def register_signals():
            """registers signals"""
            signal.signal(signal.SIGTERM, self.exit)

        self.logger = slack_logger.initialize("pasta_killer")
        self.logger.debug("Initializing")
        register_signals()
        self.subreddit = reddit.subreddit(subreddit)
        self.old_comments = []
        self.minimum_length = minimum_length
        self.match_threshold = match_threshold
        self.ignored_strings = ignored_strings
        self.logger.info("Initialized")

    def exit(self, signum, frame):
        """defines exit function"""
        import os
        _ = frame
        self.logger.info("Exited gracefully with signal %s", signum)
        os._exit(os.EX_OK)
        return

    def kill(self):
        import prawcore
        try:
            for comment in self.subreddit.stream.comments():
                if "discussion_thread" in comment.permalink:
                    if not comment.removed:
                        for old_comment in self.old_comments:
                            if str(comment) == str(old_comment):
                                continue
                            similarity = fuzz.ratio(comment.body.lower(), old_comment.body.lower())
                            if similarity > self.match_threshold and len(comment.body.split()) > self.minimum_length and not any(s in comment.body for s in self.ignored_strings) and not self.is_moderator(comment.author):
                                comment.mod.remove()
                                comment.author.message("Your comment was removed", "Your comment was removed as it was {}% similar to {}, thus deemed likely to be a copypasta.\n\nYou may appeal this decision by [sending the moderators a message](https://www.reddit.com/message/compose?to=%2Fr%2Fneoliberal).".format(similarity, old_comment.permalink))
                                self.logger.debug("\n".join(["Copypasta", str(similarity), str(comment.permalink), str(old_comment.permalink)]))
                                break

                    len_old_comments = len(self.old_comments)
                    if len_old_comments > 201:
                        n = len_old_comments - 201
                        self.old_comments = self.old_comments[n:]
                    self.old_comments.append(comment)
        except prawcore.exceptions.ServerError:
            self.logger.error("Server error: Sleeping for 1 minute.")
            sleep(60)
        except prawcore.exceptions.ResponseException:
            self.logger.error("Response error: Sleeping for 1 minute.")
            sleep(60)
        except prawcore.exceptions.RequestException:
            self.logger.error("Request error: Sleeping for 1 minute.")
            sleep(60)
        except Exception as e:
            self.logger.error(f"Unhandled exception: Sleeping for 1 minute.\n{e}")
            sleep(60)

    def is_moderator(self, author: praw.models.Subreddit) -> bool:
        """checks if author is a moderator"""
        return author in self.subreddit.moderator()
