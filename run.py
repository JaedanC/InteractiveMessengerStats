import dash_core_components as dcc
import dash_daq as daq
from dash import Dash
from messenger import MessengerConversation
from messenger_stats import Page, Graph, GraphSwitch
from external_graphs import *
import sys, os


def load_to_graph():
    conversations = []
    try:
        with open("to_graph.txt", "r") as f:
            for line in f.readlines():
                conversations.append(load_conversation(line.strip("\n")))
    except FileNotFoundError:
        pass
    return conversations


def load_conversation(name, path="assets/messages/inbox/"):
    convo = MessengerConversation()
    for found_file in os.listdir(path + name):
        if ".json" not in found_file:
            continue
        convo += MessengerConversation(filename=path + name + "/" + found_file)
    return convo


def main():
    app = Dash(__name__, suppress_callback_exceptions=True)
    page = Page(app)


    """Define buttons"""
    # Unused
    indicator = GraphSwitch(daq.Indicator, "led", "value", value=True, color="#00cc96")
    
    # For who_messaged_first
    clear_button = GraphSwitch(daq.StopButton, "stop", "n_clicks", n_clicks=0, buttonText="clear", label="Clear below")
    timeline_on = GraphSwitch(daq.BooleanSwitch, "timeline", "on", on=True, label='Show as a timeline')
    
    # For daily_messages
    timeline_off = GraphSwitch(daq.BooleanSwitch, "timeline", "on", on=False, label='Show as a timeline')

    # For get_any_message
    year = GraphSwitch(daq.NumericInput, "year", "value", value=2020, min=-1, max=9999, label="Year")
    month = GraphSwitch(daq.NumericInput, "month", "value", value=1, min=0, max=12, label="Month")
    day = GraphSwitch(daq.NumericInput, "day", "value", value=0, min=0, max=31, label="Day")
    hour = GraphSwitch(daq.NumericInput, "hour", "value", value=-1, min=-1, max=24, label="Hour")
    minute = GraphSwitch(daq.NumericInput, "minute", "value", value=-1, min=-1, max=60, label="Minute")
    second = GraphSwitch(daq.NumericInput, "second", "value", value=-1, min=-1, max=60, label="Second")
    
    # For most_common_words
    top_words = GraphSwitch(daq.NumericInput, "top_words", "value", value=10, min=1, max=100, label="Words to show")
    word_longer_than = GraphSwitch(daq.NumericInput, "word_longer_than", "value", value=1, min=1, max=100, label="Minimum length")
    word_match = GraphSwitch(dcc.Input, "word_match", "value", value="", type="text", placeholder="Matches", debounce=False)
    
    # For most_common_emojis
    emoji_count = GraphSwitch(daq.NumericInput, "emoji_count", "value", value=10, min=1, max=9999, label="Emojis to show")

    """Create conversations"""
    # Use the to_graph.txt
    conversations = load_to_graph()
    # OR load directly here
    # conversations.append(load_conversation("MyChat_abc123abc123"))
    print(conversations)
    
    """Create graphs"""
    graphs = []
    for convo in conversations:
        graphs += [
            Graph(convo, who_messaged_first,    on_click=who_messaged_first_on_click,   on_select=who_messaged_first_on_select, buttons=[clear_button, timeline_on]),
            Graph(convo, daily_messages,        on_click=daily_messages_on_click,       buttons=[clear_button, timeline_off]),
            Graph(convo, hourly_messages,       on_click=hourly_messages_on_click,      buttons=[clear_button]),
            Graph(convo, get_any_message,       on_click=get_any_message_on_click,      buttons=[clear_button, year, month, day, hour, minute, second]),
            Graph(convo, most_common_words,     on_click=most_common_words_on_click,    buttons=[clear_button, top_words, word_longer_than, word_match]),
            # Graph(convo, most_common_emojis,    on_click=most_common_emojis_on_click,   buttons=[clear_button, emoji_count]) # Slow
        ]

    page.add_graphs(graphs)
    page.run()


if __name__ == "__main__":
    main()
