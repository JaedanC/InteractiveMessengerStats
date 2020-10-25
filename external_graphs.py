import dash_daq as daq
import dash_html_components as html
import plotly.express as px
import plotly.graph_objects as go

# Our imports
from collections import Counter
from messenger_stats import Graph, convo_messages_to_html, log
from external_graphs import *
import json

def trace_function_template(graph, buttons):
    # The data to use
    data = graph.convo.get_function()
    
    # Get the labels
    labels = list(data.keys())
    
    # Get the values
    values = list(data.values())
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark24
    
    # Trace the data. Change Trace
    # https://plotly.com/python/creating-and-updating-figures/
    trace = go.Trace(
        x=labels,
        y=values,
        mode="",
        hovertemplate="%{x} : %{y}",
        marker=dict(
            size=10,
            color=colours
        )
    )
    
    # Create the figure and add the trace
    # https://plotly.com/python-api-reference/generated/plotly.graph_objects.Figure.html
    figure = go.Figure(
        layout=dict(
            title_text="Title",
            height=500
        )
    )
    figure.add_trace(trace)
    
    return figure

def on_click_function_template(graph, buttons, click_data):
    """Feel free to return graphs in here to. Just make sure to call
    graph.page.add_graph(Graph) before returning Graph.html in the html Div
    below.
    """
    if click_data is None:
        return
    
    # Learn how to retrieve data
    # log("on_click_function()", json.dumps(click_data, indent=2))

    # Do some sort of work on the click_data
    data = None
    data_two = None
    
    return html.Div([
        data,
        data_two
    ])

def on_select_function_template(graph, buttons, select_data):
    if select_data is None:
        return
    
    # Learn how to retrieve data
    # log("select_data_function()", json.dumps(select_data, indent=2))

    # Do some sort of work on the select_data
    data = None
    data_two = None
    
    return html.Div([
        data,
        data_two
    ])

def who_messaged_first(graph, buttons):
    # The data to use
    data = graph.convo.get_who_messaged_first()


    # Get the labels
    if buttons.get("timeline", fb=True):
        labels = list(data.keys())
    else:
        labels = [date.strftime("%d %B %Y") for date in data.keys()]


    # Get the values
    values = list(data.values())


    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark24
    
    colour_list = []
    people = list(set(values))
    for person in values:
        person_index = people.index(person)
        colour_list.append(colours[person_index % len(colours)])


    # Trace the data. Change Trace
    # https://plotly.com/python/creating-and-updating-figures/
    trace = go.Scatter(
        x=labels,
        y=values,
        # hovertemplate="%{x} : %{y}",
        mode="markers",
        marker=dict(
            size=10,
            color=colour_list
        )
    )

    # Create the figure and add the trace
    # https://plotly.com/python-api-reference/generated/plotly.graph_objects.Figure.html
    figure = go.Figure(
        layout=dict(
            title_text="Who Messaged first in {}?".format(graph.convo.title),
            height=200 + len(list(set(values))) * 25
        )
    )
    
    figure.add_trace(trace)

    return figure

def who_messaged_first_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    # If you ever want to see what data is returned when you click on an item, then
    # uncomment the statement below. The raw json will be printed to log.txt
    # log("who_messaged_first_on_click", json.dumps(click_data, indent=2))
    
    date_index = click_data["points"][0]["pointNumber"]
    messages_from_day = graph.convo.get_messages_from_date_index(date_index)

    # It is possible to return new graphs!
    new_graph = Graph(messages_from_day, hourly_messages, on_click=hourly_messages_on_click, buttons=[])
    graph.page.add_graph(new_graph)
    
    # You just need to add them to to the div like so:
    return html.Div([
        new_graph.html()
        # convo_messages_to_html(messages_from_day)
    ])

def who_messaged_first_on_select(graph, buttons, select_data):
    if select_data is None:
        return

    date_indices = [point["pointNumber"] for point in select_data["points"]]
    combined_messages_from_day = graph.convo.get_messages_from_date_index(date_indices)

    return html.Pre(combined_messages_from_day.as_messenger())

def daily_messages(graph, buttons):
    # The data to use
    daily_frequencies = graph.convo.get_daily_chat_frequencies()
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark2
    
    data = []
    for i, person in enumerate(daily_frequencies.keys()):
        # Get colour
        colour = colours[i % len(colours)]
        
        # Get the labels
        if buttons.get("timeline", True):
            labels = list(daily_frequencies[person].keys())
        else:
            labels = [m.strftime("%d %B %Y")
                      for m in daily_frequencies[person].keys()]

        # Get the values
        values = list(daily_frequencies[person].values())
        
        # https://plotly.com/python/bar-charts/
        data.append(go.Bar(
            name=person,
            x=labels,
            y=values,
            hovertemplate="%{{y}} by {} on %{{x}}".format(person),
            marker=dict(
                # color=colour
            )
        ))
    
    
    figure = go.Figure(
        data=data,
        layout=dict(
            title="Messages per day in {}".format(graph.convo.title),
            height=1000
        )
    )
    
    # Sort the xaxis.
    if not buttons.get("timeline", True):
        dates = graph.convo.get_dates()
        dates = [date.strftime("%d %B %Y") for date in dates]
        figure.update_layout(
            xaxis={
                "type": "category",
                "categoryorder": "array",
                "categoryarray": dates
            }
        )

    # Change the bar mode
    # figure.update_layout(barmode='group')
    figure.update_layout(barmode='stack')
    return figure

def daily_messages_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    
    
    person_index = click_data["points"][0]["curveNumber"]
    message_index = click_data["points"][0]["pointNumber"]
    
    person = graph.convo.participants[person_index]
    messages = graph.convo.get_messages_from_date_index(message_index, person=person)
    
    # log("daily_messages_on_click PI: {}, MI: {}, Per: {}".format(person_index, message_index, person))
    
    return html.Div([
        # html.Pre(json.dumps(click_data, indent=2)),
        convo_messages_to_html(messages)
    ])

def hourly_messages(graph, buttons):
    # The data to use
    hourly_frequencies = graph.convo.get_hourly_chat_frequencies()
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark2
    
    data = []
    for i, person in enumerate(hourly_frequencies.keys()):
        # Get colour
        colour = colours[i % len(colours)]
        
        # Get the labels
        labels = list(hourly_frequencies[person].keys())

        # Get the values
        values = list(hourly_frequencies[person].values())
        
        # https://plotly.com/python/bar-charts/
        data.append(go.Bar(
            name=person,
            x=labels,
            y=values,
            hovertemplate="%{{y}} by {} on %{{x}}".format(person),
            marker=dict(
                # color=colour
            )
        ))
    
    
    figure = go.Figure(
        data=data,
        layout=dict(
            title="Messages per hour for {}".format(graph.convo.title),
            height=1000,
            xaxis=dict(
                title="Hour (24hr)",
                tickmode='linear'
            )
        )
    )
    
    # Sort the xaxis.
    # if not buttons.get("timeline", True):
    #     dates = graph.convo.get_dates()
    #     dates = [date.strftime("%d %B %Y") for date in dates]
    #     figure.update_layout(
    #         xaxis={
    #             "type": "category",
    #             "categoryorder": "array",
    #             "categoryarray": dates
    #         }
    #     )

    # Change the bar mode
    figure.update_layout(barmode='stack')
    # figure.update_layout(barmode='group')
    return figure

def hourly_messages_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    
    person_index = click_data["points"][0]["curveNumber"]
    hour = click_data["points"][0]["x"]
    
    messages = graph.convo.get_messages_at_time(hour=hour)
    
    return html.Div([
        # html.Pre(json.dumps(click_data, indent=2)),
        convo_messages_to_html(messages)
    ])

def get_any_message(graph, buttons):
    year = buttons.get("year", fb=-1)
    month = buttons.get("month", fb=-1)
    day = buttons.get("day", fb=-1)
    hour = buttons.get("hour", fb=-1)
    minute = buttons.get("minute", fb=-1)
    second = buttons.get("second", fb=-1)
    
    messages = graph.convo.get_messages_at_time(year=year,
                                                month=month,
                                                day=day,
                                                hour=hour,
                                                minute=minute,
                                                second=second)
    
    daily_frequencies = messages.get_daily_chat_frequencies()
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark2
    
    data = []
    for i, person in enumerate(daily_frequencies.keys()):
        # Get colour
        colour = colours[i % len(colours)]
        
        # Get the labels
        if buttons.get("timeline", False):
            labels = list(daily_frequencies[person].keys())
        else:
            labels = [m.strftime("%d %B %Y")
                      for m in daily_frequencies[person].keys()]

        # Get the values
        values = list(daily_frequencies[person].values())
        
        # https://plotly.com/python/bar-charts/
        data.append(go.Bar(
            name=person,
            x=labels,
            y=values,
            # hovertemplate="%{{y}} by {} on %{{x}}".format(person),
            marker=dict(
                # color=colour
            )
        ))
    
    
    figure = go.Figure(
        data=data,
        layout=dict(
            title="Messages from selection in {}".format(graph.convo.title),
            height=1000
        )
    )
    
    # Sort the xaxis.
    if not buttons.get("timeline", False):
        dates = graph.convo.get_dates()
        dates = [date.strftime("%d %B %Y") for date in dates]
        figure.update_layout(
            xaxis={
                "type": "category",
                "categoryorder": "array",
                "categoryarray": dates
            }
        )

    # Change the bar mode
    # figure.update_layout(barmode='group')
    figure.update_layout(barmode='stack')
    return figure    

def get_any_message_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    
    year = buttons.get("year", fb=-1)
    month = buttons.get("month", fb=-1)
    day = buttons.get("day", fb=-1)
    hour = buttons.get("hour", fb=-1)
    minute = buttons.get("minute", fb=-1)
    second = buttons.get("second", fb=-1)
    
    messages = graph.convo.get_messages_at_time(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second
    )

    date_index = click_data["points"][0]["pointNumber"]
    person_index = click_data["points"][0]["curveNumber"]
    person = graph.convo.participants[person_index]
    
    messages = messages.get_messages_from_date_index(date_index, person=person)
    
    return html.Div([
        # html.Pre(json.dumps(click_data, indent=2)),
        convo_messages_to_html(messages)
    ])

def most_common_words(graph, buttons):
    # The data to use
    word_count = graph.convo.get_word_count()
    
    words_to_show = buttons.get("top_words", fb=10)
    word_longer_than = buttons.get("word_longer_than", fb=0)
    word_match = buttons.get("word_match", fb="")
    
    # word_longer_than
    new_counter = Counter()
    for word, count in word_count.items():
        if len(word) >= word_longer_than:
            new_counter[word] = count
            
    # word_match
    if word_match != "":
        new_counter_two = Counter()
        for word, count in word_count.items():
            if word_match in word:
                new_counter_two[word] = count
        new_counter = new_counter_two
        
        
    word_count = new_counter.most_common(words_to_show)
    
    # Get the labels
    labels = list(map(lambda x: x[0], word_count))
    
    # Get the values
    values = list(map(lambda x: x[1], word_count))
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark24
    
    # Trace the data. Change Trace
    # https://plotly.com/python/creating-and-updating-figures/
    trace = go.Bar(
        x=labels,
        y=values,
        # mode="",
        # hovertemplate="%{x} : %{y}",
        # marker=dict(
        #     size=10,
        #     color=colours
        # )
    )
    
    # Create the figure and add the trace
    # https://plotly.com/python-api-reference/generated/plotly.graph_objects.Figure.html
    figure = go.Figure(
        layout=dict(
            title_text="Top {} words for {} with a minimum length of {}".format(words_to_show, graph.convo.title, word_longer_than),
            height=500
        )
    )
    figure.add_trace(trace)
    
    return figure

def most_common_words_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    
    word = click_data["points"][0]["x"]
    messages_with_word = graph.convo.find_messages_with_word(word)
    
    return html.Div([
        # html.Pre(json.dumps(click_data, indent=2)),
        convo_messages_to_html(messages_with_word)
    ])

def most_common_emojis(graph, buttons):
    # The data to use
        
    emoji_count = buttons.get("emoji_count", fb=10)
    
    emoji_counts = graph.convo.get_total_emoji_counts().most_common(emoji_count)
    
    # log(emoji_counts)
    
    labels = []
    values = []
    for key, value in emoji_counts:
        labels.append(key)
        values.append(value)
    
    # The colours to use
    # https://plotly.com/python/discrete-color/#color-sequences-in-plotly-express
    colours = px.colors.qualitative.Dark24

    # Trace the data. Change Trace
    # https://plotly.com/python/creating-and-updating-figures/
    trace = go.Bar(
        x=labels,
        y=values
    )

    # Create the figure and add the trace
    # https://plotly.com/python-api-reference/generated/plotly.graph_objects.Figure.html
    figure = go.Figure(
        layout=dict(
            title_text="Most common emojis",
            height=500
        )
    )
    figure.add_trace(trace)
    
    return figure

def most_common_emojis_on_click(graph, buttons, click_data):
    if click_data is None:
        return
    
    emoji = click_data["points"][0]["x"]
    messages_with_emoji = graph.convo.find_messages_with_substring(emoji)
    
    return html.Div([
        # html.Pre(json.dumps(click_data, indent=2)),
        convo_messages_to_html(messages_with_emoji)
    ])
