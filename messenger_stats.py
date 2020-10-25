# Dash and Plotly
from dash import Dash
import dash
from dash.dependencies import Input, Output, State, MATCH, ALL, ALLSMALLER
from dash.exceptions import PreventUpdate
import dash_daq as daq
import dash_html_components as html
import dash_core_components as dcc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Our imports
from messenger import MessengerConversation
import os
import json


def log(*args, end="\n"):
    """Psuedo print function because print doesn't work while the server is
    running. Treat this like a print function. The result is sent to log.txt and
    the file is cleared whenever the program is run, or the page is hotloaded.
    """
    if not log.once:
        log.once = True
        with open("log.txt", "w") as f:
            f.write("")
    with open("log.txt", "a") as f:
        line = ", ".join(list(map(str, args)))
        f.write(line + end)
log.once = False
log()


def convo_messages_to_html(convo):
    """Converts a conversation into a beautiful html representation of the
    messages. This function will break if the conversation has more than the
    numbers of colours in "colours". This uses a css file called "messages.css"
    that is automatically loaded by Dash because it's in the assets folder.
    
    See: 
        Colour - https://plotly.com/python/discrete-color/
        Messaging css - https://www.w3schools.com/howto/howto_css_chat.asp

    Args:
        convo (MessengerConversation): The messages to convert

    Returns:
        <html>: The converted messages
    """
    # This doesn't work for large group chats cause colours will be out of range
    # We just loop around the colours and hope for the best.
    colours = px.colors.qualitative.Set3

    output_html = []
    for message in convo:
        colour = colours[convo.participants.index(message.sender) % len(colours)]
        output_html.append(
            html.Div([
                html.Span(message.time.strftime(
                    "%d %B %Y @ %X"), className="time-right"),
                html.P(message.sender),
                html.P(MediaMessage(message).html())
            ], className="chat_container", style={"background-color": colour}))
    return html.Div(output_html)


class MediaMessage:
    """Specifically used to render Messages with content.
    """
    def __init__(self, message):
        self.assets_folder = "assets/"
        
        self.gifs = self._find_gifs(message.gifs)
        self.audio = self._find_audio(message.audio)
        self.videos = self._find_videos(message.videos)
        self.photos = self._find_photos(message.photos)
        self.text = message.get_text()
    
    def _find_videos(self, videos):
        video_html = []
        for video in videos:
            uri = self._find_uri(video.uri)
            
            if uri is not None:
                video_html.append(
                    html.Video(
                        src=uri,
                        controls=True
                    )
                )
        return html.Div(video_html)
    
    def _find_photos(self, photos):
        photo_html = []
        for photo in photos:
            uri = self._find_uri(photo.uri)
            
            if uri is not None:
                photo_html.append(
                    html.Img(
                        src=uri
                    )
                )
        return html.Div(photo_html)
    
    def _find_gifs(self, gifs):
        return self._find_photos(gifs)
    
    def _find_audio(self, audio):
        audio_html = []
        for clip in audio:
            uri = self._find_uri(clip.uri)
            
            if uri is not None:
                audio_html.append(
                    html.Audio(
                        src=uri,
                        controls=True
                    )
                )
        return html.Div(audio_html)
    
    def _find_uri(self, uri):
        uri = "{}{}".format(self.assets_folder, uri)
        if not os.path.exists(uri):
            print("Error: Could not find: {}".format(uri))
            return None
        return uri
    
    def html(self):
        return html.Div([
            dcc.Markdown(self.text),
            self.gifs,
            self.audio,
            self.videos,
            self.photos,
        ])


class Page:
    """This represents Page of graphs. This class handles the initiation
    of the data inside Graph and the initialisation of the web
    server.
    
    Use add_graph(Graph) to add graphs to the page.
    When ready, call Page.run() to start to run the server.
    
    This takes in a dash.Dash.app.
    """
    def __init__(self, app):
        assert type(app) == Dash
        self.app = app
        # self.graphs = []
        self.graphes_index_dict = {}  # {index: graph}

    def run(self):
        """Runs the webserver. It registers the generic callback functions. 
        Whenever a different route is accessed get_page(pathname) is called but
        this is unused.
        """
        # Page layout
        # https://dash.plotly.com/dash-html-components
        self.app.layout = html.Div([
            dcc.Markdown("**MessengerStats**"),
            dcc.Location(id="home-page", refresh=False),
            html.Div(id="content")
        ])

        # Change route callback
        # log("home-page -> content")
        self.app.callback(
            Output("content", "children"),
            [Input("home-page", "pathname")]
        )(self.get_page)

        # On click
        self.app.callback(
            Output({"type": "on-click", "index": MATCH}, "children"),
            [Input({"type": "figure", "index": MATCH}, "clickData")],
            [State({"type": "figure", "index": MATCH}, "figure")]
        )(self.on_click)

        # On Select
        self.app.callback(
            Output({"type": "on-select", "index": MATCH}, "children"),
            [Input({"type": "figure", "index": MATCH}, "selectedData")],
            [State({"type": "figure", "index": MATCH}, "figure")]
        )(self.on_select)

        # On Button Press
        self.button_types = ["on", "n_clicks", "value"]  # TODO Add More
        inputs = [Input({"type": "button", "index": ALL}, bt)
                  for bt in self.button_types]
        self.app.callback(
            Output({"type": "graph", "index": MATCH}, "children"),
            inputs,
            [State({"type": "figure", "index": ALLSMALLER}, "figure"),
             State({"type": "figure", "index": ALL}, "figure")]
        )(self.update_graph)

        self.app.run_server(debug=True, threaded=True)

    def get_graph_index_from_figure(self, figure):
        """I embed the graph index into the uid of the graph when its created.
        This hack lets me remember which graph a figure is when it returned 
        from the callback functions.

        Args:
            figure (dict): The callback json of a figure

        Returns:
            int: The graph index
        """
        return int(figure["data"][0]["uid"])
    
    def on_click(self, click_data, figure):
        """This function is called when a graph is clicked. It returns the html
        that will be sloted into the 'on-click' id of the graph in question.

        Args:
            click_data (dict): Corresponding data about the click
            figure (dict): Dict containing data about the relevant figure

        Returns:
            <html>: What to render now that the figure has been clicked
        """
        graph_index = self.get_graph_index_from_figure(figure)
        graph = self.graphes_index_dict[graph_index]
        # log("Page.on_click() triggered for", graph_index)
        return graph.on_click(click_data)

    def on_select(self, select_data, figure):
        """This function is called when elements in the graph are selected. It
        returns the html that will be sloted into the 'on-select' id of the
        graph in question.

        Args:
            select_data (dict): Corresponding data about the selection
            figure (dict): Dict containing data about the relevant figure

        Returns:
            <html>: What to render now that data has been selected
        """
        graph_index = self.get_graph_index_from_figure(figure)
        graph = self.graphes_index_dict[graph_index]
        # log("Page.on_select() triggered for", graph_index)
        return graph.on_select(select_data)

    def update_graph(self, *graph_changes):
        """This is some of the most retarded hacky code I've ever written. The
        Dash api is complete garbage but I've managed to find way of working
        around every single thing that has blocked me so far.

        Args:
            *graph_changes. Due to the nature of the callbacks, this comes in
                three parts.
                1. All the button inputs. This will make up the majority of this
                list.
                2. All the figures in the graph that have a smaller index than
                the one that got triggered. This is used to identify which
                graph was clicked because apparently you can't use MATCH and ALL
                at the same time when you create the callbacks. This is so dumb,
                because you can use ALLSMALLER and ALL but not the other one.
                It's whatever
                3. A list of all the figures. This is used to find out which
                graphs we need to delete from the graph dictionary -> the ones
                which aren't on the screen anymore.

        Raises:
            PreventUpdate: This is raised if a KeyError is raised when accessing
                the graph dictionary. Why this happens is still unknown to me
                and it annoys the hell out of me. But it never seemed to cause
                an issue with the graph. I have a feeling the callback functions
                are firing twice, and the second time hasn't registered the
                deletion of the graph the first time.

        Returns:
            <html>: The updated graph
        """
        
        # Get each of the three components
        # log("Graph Change", json.dumps(graph_changes, indent=2))
        button_changes = graph_changes[:-2]
        smaller_figures = graph_changes[-2]
        all_figures = graph_changes[-1]

        # Get the graph indices that ARE being shown on the screen. It's
        # sorted so that the buttons line up with the graphs. This feels like
        # a gross workaround cause it is.
        applied_graph_indexes = []
        for figure in all_figures:
            applied_graph_indexes.append(
                self.get_graph_index_from_figure(figure))
        applied_graph_indexes.sort()

        # Get the graph indices that are LESS THAN the figure that called this
        # function. Sorting reason is above, but also kinda scared to not sort
        # at this point.
        smaller_figures_indexes = []
        for figure in smaller_figures:
            smaller_figures_indexes.append(
                self.get_graph_index_from_figure(figure))
        smaller_figures_indexes.sort()

        # log("Page.update_graph() smaller figures", smaller_figures_indexes)

        # Now work out the graph indices that aren't being shown and store them
        # in a list to be deleted.
        # log("Page.update_graph() showing", applied_graph_indexes)
        need_to_delete = []
        for index in self.graphes_index_dict.keys():
            if index not in applied_graph_indexes:
                need_to_delete.append(index)
        # log("Page.update_graph() deleting", need_to_delete)

        
        # The graph index is the length of the graphs with a smaller index. This
        # doesn't feel like it should work but it does. I need to watch this
        # because larger pages might expose why this doesn't work.
        graph_index = len(smaller_figures)
        # log("Page.update_graph() triggered for", graph_index)
        
        # Deleting the graphs
        # log("Page.update_graph() Before delete", self)
        for index in need_to_delete:
            self.delete_graph(index)
        # log("Page.update_graph() After delete", self)

        # Need to find the exact graph index that we clicked on
        # Sometimes raises a key error. This is bugging me so much but it seems
        # to be ignorable. I have a feeling it's calling this function twice or
        # something. IT ANNOYS ME THAT I CAN'T FIND THE ROOT OF THE PROBLEM.
        try:
            graph = self.graphes_index_dict[graph_index]
        except KeyError:
            raise PreventUpdate
        
        # Now we update all the buttons values using the button changes
        # section
        self.update_all_graph_buttons(applied_graph_indexes, *button_changes)

        # Then we call the graph to be re-rendered and the html returned.
        return graph.update_graph()

    def update_all_graph_buttons(self, applied_graph_indexes, *values):
        """This function also works by some magic and gross workarounds. The
        values that are passed in are the buttons that are only on the screen.
        Because of this, we also need to know which graphs are also on the screen.
        This is supplied through applied_graph_indexes. The values is also dumb
        too. For all the different kinds of the button inputs, eg. n_clicks, on
        etc. It provides a list of values. This list is the length of the number
        buttons on the screen despite them not aligning with that type most of the
        time. Values of None in the list mean that the button type does not apply
        to this button. By looping through each of the buttons and finding the
        "wants" that corresponds to the index in the value that isn't None, we
        can update all the values of the buttons.

        Args:
            applied_graph_indexes (list): Graph indices that are active
            *values (list): list of button types and their mapping to each
                button.
        """
        assert len(values) == len(self.button_types)

        # log("Page.update_all_graph_buttons()", applied_graph_indexes)

        # First we grab all the switches and store them in a list. If we change
        # them here, we also change them in the Graphs since they are references.
        # Awesome!
        all_graph_switches = []
        for graph_index in applied_graph_indexes:
            graph = self.graphes_index_dict[graph_index]
            all_graph_switches += graph.graph_switches

        # log()
        # log("Before")
        # log("\n".join(list(map(str, all_graph_switches))))

        # This is the magic that maps. Don't ask. It was 2am:
        # [n_clicks, on, value, blah]
        # [None, 0, None], [True, None, None], [None, None, 5], [None, None, None]
        # [b1, b2, b3]
        for i, value_list in enumerate(values):
            assert len(value_list) == len(all_graph_switches), "Expected {}. Got {}".format(
                len(value_list), len(all_graph_switches))
            # value_list = [None, 0, None]
            wants = self.button_types[i]

            for switch_idx, graph_switch in enumerate(all_graph_switches):
                if wants == graph_switch.wants and value_list[switch_idx] is not None:
                    graph_switch.set_value(value_list[switch_idx])
        # log("After")
        # log("\n".join(list(map(str, all_graph_switches))))
        # log()

    def add_graph(self, graph):
        """Finds the first valid index and then gives that value to the graph
        so that it can properly create itself. The Page is given to the Graph
        as this interaction is required.. It gets added to
        self.graphes_index_dict with the index as the key.

        Args:
            graph (Graph): Graph to add.
        """
        index = 0
        while index in self.graphes_index_dict:
            index += 1
        # log("Page.add_graph() found index", index)

        self.graphes_index_dict[index] = graph
        graph.create(self, index)
    
    def add_graphs(self, graph_list):
        for graph in graph_list:
            self.add_graph(graph)

    def delete_graph(self, graph_index):
        """Deletes a graph from self.graphes_index_dict.

        Args:
            graph_index (int): Graph index to delete

        Raises:
            ValueError: If the graph does not exist
        """
        if graph_index not in self.graphes_index_dict:
            raise ValueError("Graph index not in graph dictionary")

        del self.graphes_index_dict[graph_index]

    def get_page(self, pathname):
        """This returns the html to be rendered when the path changes. By default,
        this function will be called once and all the html of the graghs is
        constructed in here. You could use this function (and the pathname)
        parameter to serve up different pages but this functionality is unused
        at the moment.

        Args:
            pathname (str): The current route.
                Eg: If you're at http://127.0.0.1:8050/hello
                the pathname is "hello"

        Returns:
            <html>: The html to serve on this webpage.
        """
        # I just serve all the html for every graph.
        return html.Div([graph.html() for graph in list(self.graphes_index_dict.values())])

    def __repr__(self):
        """String representation. Includes the pages that are on the screen at
        the moment
        """
        indexes_as_str = list(map(str, list(self.graphes_index_dict.keys())))
        return "Page<{}>".format(", ".join(indexes_as_str))


class Graph:
    """I had to do deals with the devil to get this trash to work"""
    def __init__(self, convo, figure_function, on_click=None, on_select=None, buttons=[]):
        """This represents a graph that will go inside a Page.
        
        Args:
            convo (MessengerConversation): The conversation we're graphing
            figure_function (<function>): The function to call to trace this graph
            on_click_function (<function>): The function to call when an item on
                the graph is clicked
            on_select_function (<function>): The function to call when multiple
                items on the graph are selected.
            buttons (list(GraphSwitch)): The switches that are assigned to this graph.
        """
        self.convo = convo
        self.figure_function = figure_function
        self.on_click_function = on_click
        self.on_select_function = on_select
        
        # These are assigned in Graph.create()
        self.page = None
        self.index = None
        
        # Here the buttons are copied to self.graph_switches
        self.graph_switches = []
        assert type(buttons) == list
        for button in buttons:
            assert type(button) == GraphSwitch
            self.graph_switches.append(button.copy())
        # log("Graph.init() created {} switches".format(len(self.graph_switches)))

    def create(self, page, index):
        """The graph switches are initialised in here and are assigned a
        GraphSwitchGroup

        Args:
            page (Page): Page we're being added to.
            index (int): Our graph index
        """
        # assert type(page) == Page
        self.page = page
        assert index >= 0
        self.index = index

        for graph_switch in self.graph_switches:
            graph_switch.create(self.index)

        self.graph_switch_group = GraphSwitchGroup(self.graph_switches)

    def delete(self):
        """Deletes itself. This should only call called on temporary graphs
        """
        self.page.delete_graph(self.index)

    def on_click(self, click_data):
        """This function is called by Page from a callback. This takes in
        click_data that is dictionary containing specific data about the
        click. You can use log(json.dumps(click_data, indent=2)) to see the data.
        It then returns calls the corresponding on_click_function if it exists
        then returns the html to be rendered.

        Args:
            click_data (data): Specific data about the thing you clicked

        Returns:
            <html>: html to appear when the click happens. Eg, show messages
        """
        # log("Graph.on_click()", json.dumps(click_data, indent=2))
        if self.on_click_function is not None:
            return self.on_click_function(self, self.graph_switch_group, click_data)
        return

    def on_select(self, select_data):
        """See on_click. It's the same but for selections.
        """
        # log("Graph.on_select()", json.dumps(select_data, indent=2))
        if self.on_select_function is not None:
            return self.on_select_function(self, self.graph_switch_group, select_data)
        return

    def update_graph(self):
        """See on_click. It's the same but for when the graph needs to be
        re-rendered. For example when a button changes. This function must
        exist.
        """
        # log("Graph.update_graph() for", self)
        return self.graph_function()

    def graph_function(self):
        """Returns the html for the graph with its index. Passes the graph
        switch group to the figure_function.

        Returns:
            <html>: The graph html
        """
        figure = self.figure_function(self, self.graph_switch_group)
        
        # This is where we store/hide the graph_index in the figure. Very hacky
        # but it works.
        figure.update_traces(uid=self.index)

        return dcc.Graph(
            figure=figure,
            id={"type": "figure", "index": self.index}
        )

    def html(self):
        """Returns the complete html representation of this graph. This is
        unique because it used the graph index with "Pattern Matching Callbacks".
        The html would also contain the children of this graph.
        
        See: https://dash.plotly.com/pattern-matching-callbacks

        Returns:
            <html>: The whole graph's html.
        """
        assert self.page is not None
        assert self.index is not None
        return html.Div([
            html.Div(id={"type": "graph", "index": self.index},
                     children=self.graph_function()),
            html.Div([html.Div(gs.button, className="my_button") for gs in self.graph_switches]),
            html.Div(id={"type": "on-click", "index": self.index}),
            html.Div(id={"type": "on-select", "index": self.index}),
        ])

    def __repr__(self):
        """String representation of the graph. Shows a subset of participants
        in the conversation.
        """
        assert self.index is not None
        show_participants_count = 3
        extra = "..." if len(
            self.convo.participants) > show_participants_count else ""
        return "Graph<{}>({}{})".format(self.index, ", ".join(self.convo.participants[:show_participants_count]), extra)


class GraphSwitch:
    def __init__(self, switch, name, wants, **switch_kwargs):
        """This class represents a Plotly daq.<Switch> for the purposes of making
        my life much easier.

        See:
            https://dash.plotly.com/dash-core-components
            https://dash.plotly.com/dash-daq

        Args:
            switch (daq.Switch): A function pointer to the switch we are creating
            name (str): The name of the switch.
            wants (str): This is the property of the switch that stores all the data
                about the switch. This is what goes in the second paramter of Input().
                For a BooleanSwitch it is "on". For many it is "value"
            **kwargs: Place any data for the switch that you would normally put in
                the contructor here.
        """
        self.switch = switch
        self.name = name
        self.wants = wants
        self.switch_kwargs = switch_kwargs

        # These are defined in GraphSwitch.create()
        self.graph_index = None
        self.button = None
        
        # Error check to make sure the button is a copy.
        # This stops you from running into referencing issues if you reuse
        # the same button in graphs. Should be invisible to most people because
        # Graph() handles this for you.
        self.came_from_copy = False
        
    def __repr__(self):
        """A string representation of the GraphSwitch.
        """
        link = "UNLINKED" if self.graph_index is None else str(
            self.graph_index)
        return "GraphSwitch<{}.{}> -> {}, {}".format(self.name, self.wants, link, self.switch_kwargs)

    def create(self, graph_index):
        """Creates the buttons with the graph index.
        
        See: https://dash.plotly.com/pattern-matching-callbacks

        Args:
            graph_index (int): The graph index we're assigned to.
        """
        assert graph_index >= 0
        self.graph_index = graph_index
        self.button = self.switch(
            id={"type": "button", "index": self.graph_index},
            **self.switch_kwargs
        )
        # log("GraphSwitch.create()", self)

    def copy(self):
        """Returns a copy of this GraphSwitch. It's important that buttons are
        copied to graphs or they will have referencing issues.
        """
        graph_switch = GraphSwitch(self.switch, self.name, self.wants, **self.switch_kwargs)
        graph_switch.came_from_copy = True
        return graph_switch

    def get_value(self):
        """Returns the value of the button
        """
        assert self.came_from_copy, "You need to copy this button or wierd things will happen"
        assert self.wants in self.switch_kwargs, "You forgot to add {} to the kwargs of {}".format(self.wants, self) 
        return self.switch_kwargs[self.wants]

    def set_value(self, value):
        """Sets the value of the button
        """
        assert self.came_from_copy, "You need to copy this button or wierd things will happen"
        self.switch_kwargs[self.wants] = value


class GraphSwitchGroup:
    def __init__(self, graph_switches):
        """This is what is passed into the graphing functions. This is a bundle of
        GraphSwitches. Use get() to get the values of a specific button.
        """
        # Quick type checking
        assert type(graph_switches) == list
        for graph_switch in graph_switches:
            assert type(graph_switch) == GraphSwitch

        self.graph_switch_dict = {gs.name: gs for gs in graph_switches}
        
    def __repr__(self):
        """A string representation of a GraphSwitchGroup
        """
        output = ""
        for graph_switch in self.graph_switch_dict.values():
            output += "{}\n".format(graph_switch)
        return output.strip()

    def get(self, graph_switch_name, fb=None):
        """Use this function to get the values of a button in this ButtonGroup

        Args:
            key (str): The GraphSwitch.name
            fb (<any>, optional): The fallback value if the button does not exist.
                Use this to still let graphs render a certain way even if a 
                Switch isn't present. Defaults to None.

        Returns:
            The value of the switch. Or fb if the GraphSwitch.name does not exist.
        """
        if graph_switch_name not in self.graph_switch_dict.keys():
            return fb
        return self.graph_switch_dict[graph_switch_name].get_value()


def main():
    pass

if __name__ == "__main__":
    main()
