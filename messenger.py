import json
import datetime
from collections import Counter
from collections import deque
import emoji
import threading
import time

# These characters are trimmed to make word counts.
forbidden = "!@#$%^&*()-_=+[]{{}}\\|;:'\",<.>/?`~\t\r"

# These weird characters (key) are swapped for better characters (value)
convert = {
    "â\x80\x99": "'",  # \u00e2\u0080\u0099 raw
    "â\x80\x9c": '"',
    "👋": "",  # Duplicate for some reason
    "â\x80\x9d": '"'
}

def convert_unicode(string):
    for key, item in convert.items():
        string = string.replace(key, item)
    return string.encode('raw_unicode_escape').decode('utf-8')


def convert_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp)


class Message:
    class Reactions:
        def __init__(self, reaction_json):
            self.emoji = convert_unicode(reaction_json["reaction"])
            self.reactor = convert_unicode(reaction_json["actor"])
            
    class Gif:
        def __init__(self, gif_json):
            self.uri = gif_json["uri"]
            
    class Audio:
        def __init__(self, audio_json):
            self.uri = audio_json["uri"]
            self.time = convert_timestamp(audio_json["creation_timestamp"])

    class Video:
        def __init__(self, video_json):
            self.uri = video_json["uri"]
            self.time = convert_timestamp(video_json["creation_timestamp"])
            self.thumbnail = video_json["thumbnail"]["uri"]

    class Photo:
        def __init__(self, photo_json):
            self.uri = photo_json["uri"]
            self.time = convert_timestamp(photo_json["creation_timestamp"])
    
    class Content:
        def __init__(self, content):
            self.raw_text = content
            self.text, clean = self._clean_content(content)
            
            self.word_list = [word for word in clean.split() if word != ""]
            # for word in clean.split():
            #     if word != "":
            #         self.word_list.append(word)
            self.word_count = Counter(self.word_list)
        
        def _clean_content(self, raw_content):
            converted = convert_unicode(raw_content)
            clean = converted.replace("\n", " ").lower()
            for forbidden_character in forbidden:
                clean = clean.replace(forbidden_character, "")
            return converted, clean
    
    def __init__(self, json_data):
        self.sender = convert_unicode(json_data["sender_name"])
        self.time = convert_timestamp(json_data["timestamp_ms"] // 1000)

        self.reactions = self._read_reactions(json_data)
        self.gifs = self._read_gifs(json_data)
        self.audio = self._read_audio(json_data)
        self.videos = self._read_videos(json_data)
        self.photos = self._read_photos(json_data)
        self.content = self._read_content(json_data)

    def _read_reactions(self, json_data):
        if "reactions" not in json_data:
            return []
        return [self.Reactions(data) for data in json_data["reactions"]]
    
    def _read_gifs(self, json_data):
        if "gifs" not in json_data:
            return  []
        return [self.Gif(data) for data in json_data["gifs"]]
    
    def _read_audio(self, json_data):
        if "audio_files" not in json_data:
            return []
        return [self.Audio(data) for data in json_data["audio_files"]]
    
    def _read_videos(self, json_data):
        if "videos" not in json_data:
            return []
        return [self.Video(data) for data in json_data["videos"]]
    
    def _read_photos(self, json_data):
        if "photos" not in json_data:
            return []
        return [self.Photo(data) for data in json_data["photos"]]
    
    def _read_content(self, json_data):
        if "content" not in json_data:
            return None
        return self.Content(json_data["content"])
    
    def get_text(self):
        if self.content is not None:
            return self.content.text
        return ""

    def get_raw_text(self):
        if self.content is not None:
            return self.content.raw_text
        return ""
    
    def has_media(self):
        return self.gifs != [] or self.audio != [] or \
            self.videos != [] or self.photos != []
    
    def __repr__(self):
        max_line_length = 100
        show_text = self.get_text()[:max_line_length] + \
            ("..." if len(self) >= max_line_length else "")
        return "{}: {}: {}".format(self.time, self.sender, show_text)

    def __iter__(self):
        self.i = -1
        return self

    def __next__(self):
        self.i += 1
        if self.i == len(self):
            raise StopIteration
        return self.get_text()[self.i]

    def __getitem__(self, key):
        return self.get_text()[key]

    def __len__(self):
        return len(self.get_text())

    def split(self, line_length):
        """Returns the message as a list of strings word wrapped by line_length

        Args:
            line_length (int): Word wrap characters

        Returns:
            list(str): Word wrapped content
        """
        lines = []
        line = ""
        word = ""
        for char in self.get_text():
            if char == "\n":
                line += word
                lines.append(line)
                line = ""
                word = ""
                continue

            if len(word) > line_length:
                lines.append(word[:line_length])
                word = word[line_length:]
                continue
            
            if len(line) + len(word) > line_length:
                lines.append(line)
                line = ""
                word += char
                continue
            

            if char == " ":
                line += word + " "
                word = ""
                continue

            word += char
        line += word
        lines.append(line)
        # lines.append("_" * line_length)
        
        for i in range(len(lines)):
            lines[i] = lines[i].ljust(line_length, " ")
        
        return lines
    
    def all_text(self):
        return "{}: {}: {}".format(self.time, self.sender, self.get_text())
    
    def get_word_count(self):
        if self.content is None:
            return Counter()
        return self.content.word_count

    def get_word_list(self):
        if self.content is None:
            return []
        return self.content.word_list


class MessengerConversation:
    def __init__(self, filename=None, messages=None, participants=None, title=None):
        assert filename is None or type(filename) == str
        assert messages is None or type(messages) == list
        if type(participants) == str:
            participants = [participants]
        assert participants is None or type(participants) == list
        assert title is None or type(title) == str
        
        self.participants = []
        self.messages = []
        self.title = title
        self._parse_json(filename)
        self._load_preexisting_messages(messages, participants)

        self._personal_emoji_counts = None
        self._total_emoji_counts = None
        self._get_word_count_buffer = None

    def _parse_json(self, filename):
        # Read Json file
        if filename is not None:
            # rb stops weird decoding issues
            # Allowing FileNotFoundError to be thrown
            with open(filename, "rb") as f:
                json_dump = json.loads(f.read())

            for person in json_dump["participants"]:
                self.participants.append(convert_unicode(person["name"]))

            for message in json_dump["messages"]:
                self.messages.append(Message(message))
            
            # Title
            if json_dump["thread_type"] == "Regular":
                self.title = " and ".join(self.participants) + "'s chat"
            else:
                self.title = convert_unicode(json_dump["title"])
    
    def _load_preexisting_messages(self, messages, participants):
        if participants is not None:
            for person in participants:
                if person not in self.participants:
                    self.participants.append(person)
        
        # Assign preexisting messages
        if messages is not None:
            self.messages += messages
        
        # Add any participants in the messages that we may have forgotten about
        for message in self.messages:
            if message.sender not in self.participants:
                self.participants.append(message.sender)
        
        # Sort the messages by the date
        self.messages.sort(key=lambda x: x.time)
    
    def __repr__(self):
        """A brief summary of the people involved in the conversation
        """
        self.participants.sort()
        if len(self.participants) > 2:
            people = "in {} with {} and {}".format(self.title, ", ".join(self.participants[:-1]), self.participants[-1])
        elif len(self.participants) == 2:
            people = "with " + " and ".join(self.participants)
        elif len(self.participants) == 1:
            people = "with {}".format(self.participants[0])
        else:
            people = "no one?"
        return "A {} message conversation {}.".format(len(self.messages), people)
    
    def __add__(self, other):
        """Adding two MessengerConversations combines them into one. The participants and messages
        are merged into one with the new conversation returned from the operation. The existing
        conversations are not modified.

        Args:
            other (MessengerConversation): The conversation to add

        Returns:
            [MessengerConversation]: The merged conversation
        """
        
        new_participants = []
        new_participants += self.participants
        new_participants += other.participants
        new_participants = list(set(new_participants))
        
        # New title
        if self.title == None and other.title == None:
            title == None
        elif self.title == None:
            title = other.title
        elif other.title == None:
            title = self.title
        elif self.title == other.title:
            title = self.title
        else:
            title = "{} + {}".format(self.title, other.title)

        return MessengerConversation(
            messages=self.messages + other.messages,
            participants=new_participants,
            title=title
        )

    def __iter__(self):
        """Used to iterate over all the messages in the conversation
        """
        self.i = -1
        return self
    
    def __next__(self):
        """Returns the next message in the conversation
        """
        self.i += 1
        if self.i == len(self.messages):
            raise StopIteration
        return self.messages[self.i]

    def __getitem__(self, key):
        return self.messages[key]

    def as_messenger(self, line_max=64):
        """Returns a string which is a prettified version of all the messages.
        Each message returns their '.split' method which actually returns the
        message word wrapped to line_max. Then the left padding is added to make
        all the messages line up.

        Args:
            line_max (int, optional): Word wrap characters. Defaults to 64.

        Returns:
            str: Prettified messages in str format.
        """
        # Name padding
        longest_name = 0
        for person in self.participants:
            if len(person) > longest_name:
                longest_name = len(person)
        
        # Time padding
        # 2020-06-28 07:09:19.250597 # Remove the decimal
        time_now = datetime.datetime.now().__str__().split(".")[0]
        padding = len("{}: ".format(time_now)) + longest_name + 3
        
        output = ""
        for message in self.messages:
            lines = message.split(line_max)
                    
            left = [" " * padding for _ in range(len(lines))]            
            left[0] = "{}: {}:".format(message.time, message.sender).ljust(padding, " ")
            
            for i in range(len(lines)):
                lines[i] = lines[i].ljust(line_max)
            
            for i in range(len(lines)):
                output += left[i] + lines[i] + "\n"
        return output

    def first(self):
        """Returns the time of the first message ever sent.
        """
        current_min = None
        for message in self.messages:
            if current_min is None:
                current_min = message.time

            if message.time < current_min:
                current_min = message.time
        return current_min

    def last(self):
        """Returns the time of the last message ever sent
        """
        current_max = None
        for message in self.messages:
            if current_max is None:
                current_max = message.time

            if message.time > current_max:
                current_max = message.time
        return current_max
    
    def get_participants_from_message_order(self):
        participants = []
        for message in self.messages:
            if message.sender not in participants:
                participants.append(message.sender)
        return participants
    
    def find_messages_with_substring(self, substring, case_sensitive=False):
        """Finds the messages that contain the substring. Ignores case by
        default.

        Args:
            substring (str): The search substring
            case_sensitive (bool, optional): Defaults to False.

        Returns:
            MessengerConversation: Containing only the found messages (useful
                for further analysis)
        """
        found_messages = []
        for message in self.messages:
            message_text = message.get_text()
            
            if not case_sensitive:
                message_text = message_text.lower()
                substring = substring.lower()
                
            if substring in message_text:
                found_messages.append(message)
        return MessengerConversation(messages=found_messages,
                                     participants=self.participants,
                                     title=self.title)

    def find_messages_with_word(self, word):
        """Find messages containing the specfic word. This mustn't be confused
        with find_messages_with_substring. This is one word with punctuation
        removed. For example, "wont"
        
        Args:
            word (str): The search word

        Returns:
            MessengerConversation: Containing only the found messages.
        """
        found_messages = []
        for message in self.messages:
            if word.lower() in message.get_word_list():
                found_messages.append(message)
        return MessengerConversation(messages=found_messages,
                                     participants=self.participants,
                                     title=self.title)

    def get_all_personal_messages(self):
        """Returns a dictionary of participants as the keys, and the stored
        value is the list containing the messages they wrote.

        Returns:
            dict -> str : list
                 -> person : [<Message>, <Message>]
        """
        return {person: self.get_personal_messages(person) for person in self.participants}

    def get_personal_messages(self, person):
        """Returns a MessengerConversation with only the messages from 'person'

        Args:
            person (str): Person
        
        Throws:
            AssertionError if the person is not in this MessengerConversation

        Returns:
            MessengerConversation: Containing only the person's messages
        """
        assert person in self.participants, "{} not in {}".format(person, self)
        messages = list(filter(lambda m: m.sender == person, self.messages))
        return MessengerConversation(messages=messages, participants=[person], title=self.title)
        
    def get_daily_chat_frequencies(self): 
        """Returns a dictionary containing the messages counts per day
        for each person.

        Returns:
            dict -> str : Counter(datetime.datetime : int)
                 -> person : Counter(date : count)
        """
        individual_message_count = {}
        for person in self.participants:
            messages = self.get_personal_messages(person)
            message_count = Counter([message.time.date() for message in messages])
            individual_message_count[person] = message_count
        return individual_message_count
    
    def get_hourly_chat_frequencies(self):
        hourly_frequencies = {}
        for person in self.participants:
            messages = self.get_personal_messages(person)
            hourly_frequencies[person] = Counter([message.time.hour for message in messages])
        return hourly_frequencies

    def get_weekday_chat_frequencies(self):
        weekday_frequencies = {}
        for person in self.participants:
            messages = self.get_personal_messages(person)
            weekday_frequencies[person] = Counter([message.time.strftime("%A") for message in messages])
        return weekday_frequencies

    def get_dates(self):
        """Returns a sorted list of dates for every message ever sent.

        Returns:
            list(datetime.datetime): List of dates
        """
        dates = list(set([message.time for message in self.messages]))
        dates.sort()
        return dates
    
    def get_word_count(self):
        """Returns a counter containing the counts of every single word in the
        conversation.
        """
        if self._get_word_count_buffer is not None:
            return self._get_word_count_buffer
        
        message_word_counts = []
        for message in self.messages:
            message_word_counts += message.get_word_list()
        self._get_word_count_buffer = Counter(message_word_counts)
        return self._get_word_count_buffer
    
    def get_messages_at_time(self, year=None, month=None, day=None, hour=None, minute=None, second=None):
        """Returns a filtered list of messages that match the time input. At
        least one field must be set or it will return [].

        Args:
            <time> (int, optional): Defaults to None.

        <time> can be year, month, day, hour, minute, second (if you really want lmao)

        Returns:
            MessengerConversation : Containing the matching messages
        """
        messages = self.messages
        if year is None and month is None and day is None and hour is None \
            and minute is None and second is None:
            return self
        
        if year is not None and year >= 0:
            messages = list(filter(lambda x: x.time.year == year, messages))
        
        if month is not None and month > 0:
            messages = list(filter(lambda x: x.time.month == month, messages))
        
        if day is not None and day > 0:
            messages = list(filter(lambda x: x.time.day == day, messages))
        
        if hour is not None and hour >= 0:
            messages = list(filter(lambda x: x.time.hour == hour, messages))
        
        if minute is not None and minute >= 0:
            messages = list(filter(lambda x: x.time.minute == minute, messages))
        
        if second is not None and second >= 0:
            messages = list(filter(lambda x: x.time.second == second, messages))
        
        return MessengerConversation(messages=messages,
                                     participants=self.participants,
                                     title=self.title)
    
    def get_time_range(self, start, end, inclusive=True):
        """Returns the messages from inside the range [start, end] unless
        exclusive is set to False, then it is [start, end). Can also set start
        or end to be None and it will consider all no limit on that side.

        Args:
            start (datetime.datetime): Start date
            end (datetime.datetime): End date

        Returns:
            MessengerConversation: Containing the range of messages
        """
        found_range = []
        
        if start is None and end is None:
            return self
        
        for message in self.messages:
            if end is None:
                before_end = True
            elif inclusive:
                before_end = message.time <= end
            else:
                before_end = message.time < end
            
            if start is None:
                after_start = True
            else:
                after_start = message.time >= start
            
            if after_start and before_end:
                found_range.append(message)
        return MessengerConversation(messages=found_range,
                                     participants=self.participants,
                                     title=self.title)
    
    def get_messages_from_date_index(self, indexes, person=None):
        """Sometimes you may want to retrieve some messages from specific "date indexes"
        from a specific person. For example, indexes=[2, 5, 6, 8]. This is asking for
        the messages on the 2nd, 5th, 6th and 8th days that a message occured. This is used
        in plotly to retrieve the messages from a specific person because clicking on a
        person returns a list of date indexes if the entire conversation is plotted in
        chronological order. The return value of this method can then have the content
        retrieved and displays in pretty html format.

        Args:
            indexes (int): Date indexes
            person (str, optional): Person's messages only. Defaults to None.

        Returns:
            MessengerConversation: Containing all messages from the dates in the date
                                   indexes list
        """
        if person is not None:
            conversation = self.get_personal_messages(person)
        else:
            conversation = self
            
        all_dates = conversation.get_dates()
        all_dates = list(set([date.date() for date in all_dates]))
        all_dates.sort()
        
        # print(conversation)
        # print(conversation.as_messenger())
        # print([m.strftime("%d %B %Y") for m in all_dates])
        
        # Make indexes a list
        if type(indexes) == int:
            indexes = [indexes]
        
        for index in indexes:
            assert 0 <= index < len(all_dates)
        
        convos_from_indexes = []
        for index in indexes:
            selected_date = all_dates[index]

            convos_from_indexes.append(self.get_messages_at_time(
                year=selected_date.year,
                month=selected_date.month,
                day=selected_date.day
            ))

        return sum(convos_from_indexes, MessengerConversation(title=self.title))

    def get_who_messaged_first(self):
        """Returns an dictionary containing the unique dates and the person
        who sent the first message on that day.

        Returns:
            Dict -> datetime.date : str
                 -> date : sender
        """
        who_sent_first = {}
        for message in self.messages:
            if message.time.date() not in who_sent_first:
                who_sent_first[message.time.date()] = message.sender
        return who_sent_first

    def get_all_emoji_counts(self):
        """Returns a tuple of (get_total_emoji_counts, get_personal_emoji_counts)
        """
        # Dictionary containing Counters of individual emoji counts
        personal_emoji_counts = self.get_personal_emoji_counts()
        
        # Counter containing all emoji counts
        total_emoji_counts = self.get_total_emoji_counts()
        
        return total_emoji_counts, personal_emoji_counts

    def get_personal_emoji_counts(self):
        """Returns dictionary containing counters for each person for all their
        emoji counts. Caches the result as it is very computationally expensive.
        Uses multithreading to achieve a speed up.

        Returns:
            dict -> str : Counter(str : int)
                    person : Counter(emoji : count)
        """
        if self._personal_emoji_counts is not None:
            return self._personal_emoji_counts
        
        self._personal_emoji_counts = {}
        
        return_queue = deque()
        
        def _get_persons_emoji_count(person):
            my_messages = list(filter(lambda x: x.sender == person, self.messages))
            emoji_counts = {e: 0 for e in emoji.EMOJI_UNICODE.values()}
            for message in my_messages:
                for e in emoji_counts.keys():
                    # emoji_counts[e] += message.text.count(e)
                    emoji_counts[e] += message.get_text().count(e)
            return_queue.append((person, Counter(emoji_counts)))
        
        personal_threads = []
        for person in self.participants:
            thread = threading.Thread(target=_get_persons_emoji_count, args=(person, ))
            personal_threads.append(thread)
            thread.start()
        
        for thread in personal_threads:
            thread.join()
        
        while len(return_queue) != 0:
            result = return_queue.pop()
            self._personal_emoji_counts[result[0]] = result[1]
            
        return self._personal_emoji_counts
    
    def get_total_emoji_counts(self):
        """Returns Counter containing the counts of all the emojis

        Returns:
            Counter -> str : int
                    -> emoji : count
        """
        if self._total_emoji_counts is not None:
            return self._total_emoji_counts

        total_emoji_counts = {e: 0 for e in emoji.EMOJI_UNICODE.values()}
        for message in self.messages:
            for e in total_emoji_counts.keys():
                total_emoji_counts[e] += message.get_text().count(e)
        
        # Filter emojis counts == 0
        total_emoji_counts = dict(filter(lambda item: item[1] > 0, total_emoji_counts.items()))
        self._total_emoji_counts = Counter(total_emoji_counts)
        
        return self._total_emoji_counts
    
    
def main():
    your_convo = MessengerConversation("hangs.json")
    # your_convo = MessengerConversation("message_2.json")
    
    # print(your_convo)
    
    # print(your_convo.as_messenger(line_max=64))
    
    # print(your_convo.get_word_count())
    
    print(your_convo.get_total_emoji_counts())
    
    # start = datetime.datetime(year=2020, month=4, day=1)
    # end = datetime.datetime(year=2020, month=5, day=31)
    # your_convo = your_convo.get_time_range(start, end)
    # print(your_convo.as_messenger())
    
    # print(your_convo.find_messages_with_substring("hello").as_messenger())
    
    # print(your_convo.get_messages_at_time(day=1).as_messenger())
    pass

if __name__ == "__main__":
    main()
