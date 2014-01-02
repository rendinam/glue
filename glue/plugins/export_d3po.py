import json
import os

from astropy.table import Table

from ..config import exporters
from ..qt.widgets import ScatterWidget, HistogramWidget


D3PO_BASE = '/Users/beaumont/d3po'


def save_page(page, label):
    """ Convert a tab of a glue session into a D3PO page

    :param page: Tuple of scatter viewers on the page
    :param label: Tab label
    """
    result = {}
    result['grid'] = {'nRows': 1, 'nColumns': len(page)}
    result['name'] = str(label)
    result['caption'] = 'Generated by Glue'
    result['plots'] = map(save_plot, page, range(len(page)))

    d = page[0]._data[0]
    unselected = dict(opacity=d.style.alpha,
                      size=d.style.markersize,
                      color=d.style.color)
    result['markerStyle'] = dict(unselected=unselected)

    has_subset = len(page[0]._data[0].subsets) == 1
    if has_subset:
        s = d.subsets[0].style
        selected = dict(opacity=s.alpha, size=s.markersize, color=s.color)
        result['markerStyle']['selected'] = selected
        result['selection'] = {'type': 'booleanColumn',
                               'columnName': 'selection'}
    result['histogramStyle'] = result['markerStyle']

    return result


def save_plot_base(plot, index):
    result = {}
    result['gridPosition'] = [0, index]
    return result


def save_plot(plot, index):
    dispatch = {ScatterWidget: save_scatter,
                HistogramWidget: save_histogram}
    typ = type(plot)
    return dispatch[typ](plot, index)


def save_scatter(plot, index):
    """ Convert a single glue scatter plot to a D3PO plot

    :param plot: Glue scatter plot
    :class:`~glue.qt.widgets.scatter_widget.ScatterWidget`
    :param index: 1D index of plot on the page
    :type index: int

    :rtype: json-serializable dict
    """
    result = save_plot_base(plot, index)
    props = plot.properties
    result['type'] = 'scatter'
    result['xAxis'] = dict(columnName=props['xatt'].label,
                           range=[props['xmin'], props['xmax']])
    result['yAxis'] = dict(columnName=props['yatt'].label,
                           range=[props['ymin'], props['ymax']])
    #XXX log scales
    return result


def save_histogram(plot, index):
    result = save_plot_base(plot, index)
    props = plot.properties
    result['type'] = 'histogram'
    result['xAxis'] = dict(columnName=props['component'].label,
                           bins=props['nbins'],
                           range=[props['xmin'], props['xmax']])
    #XXX normed, cumultive, log
    return result


def can_save_d3po(application):
    dc = application.session.data_collection

    if len(dc) != 1:
        raise ValueError("D3PO Export only supports a single dataset")
    data = dc[0]

    if len(data.subsets) > 1:
        raise ValueError("D3PO Export only supports a single subset")

    for tab in application.viewers:
        for viewer in tab:
            if not isinstance(viewer, (ScatterWidget, HistogramWidget)):
                raise ValueError("D3PO Export only supports scatter "
                                 "and histogram plots")
    if sum(len(tab) for tab in application.viewers) == 0:
        raise ValueError("D3PO Export requires at least one scatterplot "
                         "or histogram")


def save_d3po(application, path):
    """Save a Glue session to a D3PO bundle.

    Currently, this has the following restrictions:
    - The Glue session must have only one dataset open, and 0 or 1 subsets
    - Only scatter plots are present

    :param application: Glue appication to save
    :param path: Path to directory to save in. Will be created if needed
    """

    if not os.path.exists(path):
        os.mkdir(path)

    data = application.session.data_collection[0]

    subset = None
    if len(data.subsets) == 1:
        subset = data.subsets[0]

    #write the csv file
    data_path = os.path.join(path, 'data.csv')

    t = Table([data[c] for c in data.components],
              names=[c.label for c in data.components])

    if subset is not None:
        t['selection'] = subset.to_mask().astype('i')

    t.write(data_path, format='ascii', delimiter=',')

    result = {}
    result['filename'] = 'data.csv'
    result['title'] = "Glue export of %s" % data.label
    result['states'] = map(save_page, application.viewers,
                           application.tab_names)

    state_path = os.path.join(path, 'states.json')
    with open(state_path, 'w') as outfile:
        json.dump(result, outfile, indent=2)

    #write the html
    html_path = os.path.join(path, 'index.html')
    with open(html_path, 'w') as outfile:
        outfile.write(HTML)

    #show the result
    launch(path)


def launch(path):
    """Start a server to view an exported D3PO bundle, and open a browser.

    :param path: The TLD of the bundle
    """
    from SocketServer import TCPServer
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from random import randrange
    from socket import error
    import webbrowser
    from threading import Thread

    os.chdir(path)

    while True:
        try:
            PORT = randrange(8000, 9000)
            server = TCPServer(("", PORT), SimpleHTTPRequestHandler, False)
            server.allow_reuse_address = True
            server.server_bind()
            break
        except error:  # port already taken
            pass

    print 'Serving D3PO on port 0.0.0.0:%i' % PORT
    server.server_activate()

    thread = Thread(target=server.serve_forever)
    thread.setDaemon(True)  # do not prevent shutdown
    thread.start()
    webbrowser.open('http://0.0.0.0:%i' % PORT)


exporters.add('D3PO', save_d3po, can_save_d3po, directory=True)


HTML = """
<!DOCTYPE html>

<html>
<head>
<meta charset="utf-8" />

<link rel="stylesheet" type="text/css" href="http://deimos.astro.columbia.edu:5000/static/css/style.css">
<link rel="stylesheet" type="text/css" href="http://deimos.astro.columbia.edu:5000/static/css/d3po.css">
<link href='http://fonts.googleapis.com/css?family=Source+Sans+Pro:100,200,300,400,700' rel='stylesheet' type='text/css'>

<style>
#footer {
position: fixed;
bottom: 0;
right: 0;
}
</style>
<!-- not to be confused with Planet Telex -->

<!-- Javscript dependencies -->
<script src="http://d3js.org/d3.v3.min.js" charset="utf-8"></script>
<script src="http://deimos.astro.columbia.edu:5000/static/js/util.js"></script>
<script src="//ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js"></script>
<script src="http://deimos.astro.columbia.edu:5000/static/js/d3po.js"></script>
<script src="http://deimos.astro.columbia.edu:5000/static/js/d3po.init.js"></script>
</head>

<body>
<div id="svg"><svg></svg></div>
<div id="controls">
<ul class="navigation">
</ul>
</div>
<div id="caption"></div>

<div id="footer">
More information: <a href="http://d3po.org">d3po.org</a>
</div>

<script type="text/javascript">
$(document).ready(function() {
initialize('states.json', 'data.csv');
}
);
</script>
</body>
</html>
"""
