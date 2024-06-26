import numpy as np
import scipy.special as special
from . import graphics as m2graphics
from matplotlib.animation import FuncAnimation


# This class stores some data about the current labelling operation
class Labeller():
    def __init__(self, options=None):
        # List of the points of the line being drawn
        self.points = []
        # Is the control key pressed?
        self.control = False
        # IDs of the events attached to the figure
        self.binds = []
        # The app's options
        self.options = options
        # The animator object
        self.ani = None


# This function is used to handle the user pressing a mouse key
# while in the graphing area
def onclick(event, labeller, line_plot, temp_line, fringes, canvas, fig, ax, ani):
    # If this was a single click within the graphing area, add a point
    # to the line
    if labeller.control and not event.dblclick and event.xdata:
        labeller.points.append([event.ydata, event.xdata])
        # We use the points list to draw a line on the graph
        points = np.array(labeller.points)
        line_plot.set_data(points[:, 1], points[:, 0])
        # If the event was a double click, label the fringes and clear the data
        # related to the current labelling operation
        if event.button == 3:
            label_fringes(labeller, fringes, canvas, fig, ax)
            labeller.points = []
            line_plot.set_data([], [])
            temp_line.set_data([], [])
            # This clears the blit cache and redraws the figure
            ani._blit_cache.clear()
            fig.canvas.draw()


# This uses the set of points chosen by the user to label the fringes
def label_fringes(labeller, fringes, canvas, fig, ax):
    # Create two empty lists of x and y coordinates that we will be
    # iterating over
    x = []
    y = []
    # For every pair of points chosen by the user, create a set of pixels
    # to check that goes in a line between them
    for i in range(1, len(labeller.points)):
        # The resolution is set to be the larger of the two x or y intervals,
        # some coordinates in the other direction will be repeated.
        # The line may for example go
        #           ##
        #             ###
        #                ##
        resolution = int(np.amax([abs(labeller.points[i-1][1]-labeller.points[i][1]),
                                  abs(labeller.points[i-1][0]-labeller.points[i][0])])) + 1
        x = np.append(x, special.round(np.linspace(labeller.points[i-1][1],
                                                   labeller.points[i][1],
                                                   resolution)))
        y = np.append(y, special.round(np.linspace(labeller.points[i-1][0],
                                                   labeller.points[i][0],
                                                   resolution)))
    # Prepare for labelling. Phase and prev_index are temporarily set to -1
    phase = -1024
    prev_index = -1
    # This is an array of all the changed fringes, used to render only the
    # necessary fringes (as this is the operation that incurs the most
    # overhead here)
    fix_indices = []
    # Get the increment from a radio button variable if available
    if labeller.options is not None:
        increment = labeller.options.direction_var.get()
    else:
        increment = 1
    if increment == 2:
        # This setting is for unlabelling
        increment = 0
        phase = -2048

    # Iterate over all the points calculated previously
    for i in range(len(x)):
        # Check a range of points to make sure we are not slipping through
        # the pixels of a fringe like so:
        #      0  #
        #      0##         0 - fringe
        #     ##0          # - line
        #    #  0
        # We initially set index to -1. You may notice that this will be
        # usually overriden in the for loop that happens a few lines down.
        # This is a precaution for when the loop doesn't run at all - for
        # example the user clicked outside of the array
        index = -1
        try:
            for index in canvas.fringe_indices[int(y[i])-1:int(y[i])+1, int(x[i])]:
                # If a non-empty index found, use this and break
                if index != -1:
                    break
        # In case we go out of range, just pass
        except IndexError:
            pass
        # If the index is not -1 and not the same as the previous one, assign
        # a calculated phase to a fringe
        if index >= 0 and index != prev_index:
            if phase > -1024:
                phase += increment
                fringes.list[index].phase = phase
            elif phase != -2048:
                # This takes the value of the first fringe encountered.
                # All values after that are just increments
                phase = fringes.list[index].phase
                if phase == -2048:
                    phase = 0
                    fringes.list[index].phase = phase
            else:
                # Unlabell the fringe
                fringes.list[index].phase = phase
            fix_indices.append(index)
            # Storing this allows us to prevent labelling a fringe
            # multiple times
            prev_index = index
    # If the maximum phase reached in this labelling series is higher than
    # the one stored, update that. This is used to update the colour range
    if labeller.options is not None:
        if labeller.options.direction_var.get() == 1:
            if phase > fringes.max:
                fringes.max = phase
        elif labeller.options.direction_var.get() == -1:
            if phase < fringes.min:
                fringes.min = phase
    else:
        if phase > fringes.max:
            fringes.max = phase
    # Render and show the changed fringes
    if labeller.options is not None:
        width = labeller.options.width_var.get()
    else:
        width = 3
    m2graphics.render_fringes(fringes, canvas, width=width, indices=fix_indices)
    canvas.imshow.set_data(np.ma.masked_where(canvas.fringe_phases_visual == -1024, canvas.fringe_phases_visual))
    # The small increment is included to make the limits work when all fringes
    # are unlabelled
    canvas.imshow.set_clim(fringes.min, fringes.max+0.0000000001)
    canvas.imshow.figure.canvas.draw_idle()
    # This (when uncommented) allows one to see the pixels the labelling line
    # went through. Useful for debugging
    # ax.plot(x,y)


# If the mouse moves in the graph area and a line has begun, make a part
# of the line move after the mouse
def onmove(event, labeller, line_plot, temp_line, ax):
    if len(labeller.points) and event.inaxes == ax:
        # Note that we are not actually modifying labeller.points here
        points = np.array([labeller.points[-1], [event.ydata, event.xdata]])
        temp_line.set_data(points[:, 1], points[:, 0])
        # The FuncAnimation will render this, we just update data here


# Store whether the control key is pressed
def onpress(event, labeller, line_plot, temp_line):
    if event.key == 'control':
        labeller.control = True
    elif event.key == 'ctrl+backspace' or event.key == 'backspace':
        # This deletes the point that has been placed last
        labeller.points = labeller.points[:-1]
        # If there are points to display, display them. If not,
        # set the data to empty lists
        if len(labeller.points):
            points = np.array(labeller.points)
            line_plot.set_data(points[:, 1], points[:, 0])
        else:
            line_plot.set_data([], [])
            temp_line.set_data([], [])
        line_plot.figure.canvas.draw_idle()


def onrelease(event, labeller):
    if event.key == 'control':
        labeller.control = False


# This update function is used in the animation. It doesn't do stuff, but
# it returns the objects that need to be redrawn. i is the frame number
def ani_update(i, line_plot, temp_line, imshow, prev_lim, ax, labeller):
    if prev_lim != [ax.get_xlim(), ax.get_ylim()]:
        # If the limits change, do a redraw. This is slooow, but actually works
        # (the slight overhead with scrolling is worth it, as we get
        # significant improvements when drawing lines)
        prev_lim[0], prev_lim[1] = ax.get_xlim(), ax.get_ylim()
        labeller.ani._blit_cache.clear()
        imshow.figure.canvas.draw()
    return line_plot, temp_line


# This sets up the labeller object, the line that is drawn, as well as
# attaches all the event handlers
def label(fringes, canvas, fig, ax, master=None, options=None, imshow=None, mframe=None):
    labeller = Labeller(options=options)
    line_plot, = ax.plot([], [], "--", animated=True)
    temp_line, = ax.plot([], [], "--", animated=True)
    b0 = fig.canvas.mpl_connect('button_press_event',
                                lambda event: onclick(event, labeller, line_plot, temp_line,
                                                 fringes, canvas, fig, ax, labeller.ani))
    b1 = fig.canvas.mpl_connect('motion_notify_event',
                                lambda event: onmove(event, labeller, line_plot, temp_line, ax))
    b2 = fig.canvas.mpl_connect('key_press_event',
                                lambda event: onpress(event, labeller, line_plot, temp_line))
    b3 = fig.canvas.mpl_connect('key_release_event',
                                lambda event: onrelease(event, labeller))
    labeller.binds = [b0, b1, b2, b3]
    # Create an animation function that updates the state of the line
    # that is being drawn. blit is used to speed things up. It's cache
    # has to be cleared when fringe labelling is changed
    prev_lim = [ax.get_xlim(), ax.get_ylim()]
    labeller.ani = FuncAnimation(fig, ani_update, interval=100,
                                 fargs=(line_plot, temp_line, imshow,
                                        prev_lim, ax, labeller), blit=True, cache_frame_data=False)
    if mframe is not None:
        mframe.ani = labeller.ani
    # This is needed for the animation to start.
    # Because reasons
    # I guess
    fig.canvas.draw()
    return labeller


def stop_labelling(fig, labeller, mframe=None):
    labeller.ani._stop()
    if mframe is not None:
        mframe.ani = None
    for bind in labeller.binds:
        fig.canvas.mpl_disconnect(bind)
    del labeller
