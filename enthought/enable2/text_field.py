# Standard library imports
from math import floor

# Enthought library imports
from enthought.traits.api import (Str, Bool, Int, Event, Instance, Any, Property,
                                  List, Delegate)
from enthought.kiva import font_metrics_provider

# Local, relative imports
from component import Component
from text_field_style import TextFieldStyle


StyleDelegate = Delegate("_style", modify=True)

class TextField(Component):
    """ A basic text entry field for Enable.
        fixme: Requires monospaced fonts.
    """

    #------------------------------------------------------------------------
    # Public traits
    #------------------------------------------------------------------------

    # The text to be edited
    text = Property(depends_on=['_text_changed'])

    # Events that get fired on certain keypresses
    accept = Event
    cancel = Event

    # Are multiple lines of text allowed?
    multiline = Bool(False)

    # The object to use to measure text extents
    metrics = Any

    #------------------------------------------------------------------------
    # Delegates for style
    #------------------------------------------------------------------------
    
    text_color = StyleDelegate
    highlight_color = StyleDelegate
    highlight_bgcolor = StyleDelegate
    font = StyleDelegate
    line_spacing = StyleDelegate
    text_offset = StyleDelegate
    cursor_color = StyleDelegate
    cursor_width = StyleDelegate
    border_visible = StyleDelegate
    border_color = StyleDelegate
    bgcolor = StyleDelegate


    #------------------------------------------------------------------------
    # Protected traits
    #------------------------------------------------------------------------

    # The style information used in drawing
    _style = Instance(TextFieldStyle, ())


    # The max width/height of the displayed text in characters
    _text_width = Property(depends_on=['_style', 'height'], 
                           cached='_height_cache')
    _text_height = Property(depends_on=['_style', 'width'], 
                            cached='_width_cache')

    # The x-y position of the cursor in the text
    _cursor_pos = List(Int)
    _old_cursor_pos = List(Int)
    _desired_cursor_x = Int

    # The text as an x-y grid, the shadow property for 'text'
    _text = List(List)
    _text_changed = Event

    # The text that is actually displayed in the editor, and its shadow values
    _draw_text = Property
    __draw_text = List(List)
    __draw_text_xstart = Int
    __draw_text_ystart = Int

    # Whether or not to draw the cursor (is mouse over box?)
    _draw_cursor = Bool(False)


    #------------------------------------------------------------------------
    # Public methods
    #------------------------------------------------------------------------

    def __init__(self, **traits):
        # This will be overriden if 'text' is provided as a trait, but it
        # must be initialized if not
        self._text = [ [] ]

        # Initialize internal tracking variables
        self.reset()
        
        # fixme: Shouldn't traits initialize these on its own?
        self._width_cache, self._height_cache = None, None

        super(TextField, self).__init__(**traits)

        if self.metrics is None:
            self.metrics = font_metrics_provider()

        # Initialize border/bg colors
        self.__style_changed()


    #------------------------------------------------------------------------
    # Interactor interface
    #------------------------------------------------------------------------

    def normal_mouse_enter(self, event):
        event.window.set_pointer('ibeam')
        self.request_redraw()
        event.handled = True

    def normal_mouse_leave(self, event):
        event.window.set_pointer('arrow')
        self.request_redraw()
        event.handled = True

    def normal_left_down(self, event):
        self.event_state = "cursor"
        self._acquire_focus(event.window)
        event.handled = True

        # Transform pixel coordinates to text coordinates
        char_width, char_height = self.metrics.get_text_extent("T")[2:]
        char_height += self._style.line_spacing
        event_x = event.x - self.x + self._style.text_offset
        event_y = self.y2 - event.y + self._style.text_offset
        x = int(round(event_x / char_width)) - 1
        if self.multiline:
            y = int(round(event_y / char_height)) - 1 
        else:
            y = 0

        # Clip x and y so that they are with text bounds, then place the cursor
        y = min(max(y, 0), len(self.__draw_text)-1)
        x = min(max(x, 0), len(self.__draw_text[y]))
        self._old_cursor_pos = self._cursor_pos
        self._cursor_pos = [ self.__draw_text_ystart + y,
                             self.__draw_text_xstart + x ]
        
    def cursor_left_up(self, event):
        # Reset event state
        self.event_state = "normal"
        event.handled = True
        self.request_redraw()

    def normal_key_pressed(self, event):
        # Save for bookkeeping purposes
        self._old_cursor_pos = self._cursor_pos

        # Normal characters
        if len(event.character) == 1:
            y, x = self._cursor_pos
            self._text[y].insert(x, event.character)
            self._cursor_pos[1] += 1
            self._desired_cursor_x = self._cursor_pos[1]
            self._text_changed = True

        # Deletion
        elif event.character == "Backspace":
            # Normal delete
            if self._cursor_pos[1] > 0:
                del self._text[self._cursor_pos[0]][self._cursor_pos[1]-1]
                self._cursor_pos[1] -= 1
                self._desired_cursor_x = self._cursor_pos[1]
                self._text_changed = True
            # Delete at the beginning of a line
            elif self._cursor_pos[0] - 1 >= 0:
                index = self._cursor_pos[0] - 1
                old_line_len = len(self._text[index])
                self._text[index] += self._text[index+1]
                del self._text[index+1]
                del self.__draw_text[index+1-self.__draw_text_xstart]
                self._cursor_pos[0] -= 1
                self._cursor_pos[1] = old_line_len
                self._desired_cursor_x = self._cursor_pos[1]
                self._text_changed = True
        elif event.character == "Delete":
            # Normal delete
            if self._cursor_pos[1] < len(self._text[self._cursor_pos[0]]):
                del self._text[self._cursor_pos[0]][self._cursor_pos[1]]
                self._desired_cursor_x = self._cursor_pos[1]
                self._text_changed = True
            # Delete at the end of a line
            elif self._cursor_pos[0] + 1 < len(self._text):
                index = self._cursor_pos[0]
                old_line_len = len(self._text[index])
                self._text[index] += self._text[index+1]
                del self._text[index+1]
                del self.__draw_text[index+1-self.__draw_text_xstart]
                self._desired_cursor_x = self._cursor_pos[1]
                self._text_changed = True
                
        # Cursor movement
        elif event.character == "Left":
            self._cursor_pos[1] -= 1
            if self._cursor_pos[1] < 0:
                self._cursor_pos[0] -= 1
                if self._cursor_pos[0] < 0:
                    self._cursor_pos = [ 0, 0 ]
                else:
                    self._cursor_pos[1] = len(self._text[self._cursor_pos[0]])
            self._desired_cursor_x = self._cursor_pos[1]
        elif event.character == "Right":
            self._cursor_pos[1] += 1
            if self._cursor_pos[1] > len(self._text[self._cursor_pos[0]]):
                self._cursor_pos[0] += 1
                if self._cursor_pos[0] > len(self._text)-1:
                    self._cursor_pos[0] -= 1
                    self._cursor_pos[1] -= 1
                else:
                    self._cursor_pos[1] = 0
            self._desired_cursor_x = self._cursor_pos[1]
        elif event.character == "Up":
            self._cursor_pos[0] -= 1
            if self._cursor_pos[0] < 0:
                self._cursor_pos[0] = 0
            else:
                self._cursor_pos[1] = min(len(self._text[self._cursor_pos[0]]), 
                                          self._desired_cursor_x)
        elif event.character == "Down":
            self._cursor_pos[0] += 1
            if self._cursor_pos[0] >= len(self._text):
                self._cursor_pos[0] = len(self._text) - 1
            else:
                self._cursor_pos[1] = min(len(self._text[self._cursor_pos[0]]), 
                                          self._desired_cursor_x)
        elif event.character == "Home":
            self._cursor_pos[1] = 0
            self._desired_cursor_x = self._cursor_pos[1]
        elif event.character == "End":
            self._cursor_pos[1] = len(self._text[self._cursor_pos[0]])
            self._desired_cursor_x = self._cursor_pos[1]

        # Special characters
        elif event.character == "Tab":
            y, x = self._cursor_pos
            self._text[y] = self._text[y][:x] + [" "]*4 + self._text[y][x:]
            self._cursor_pos[1] += 4
            self._desired_cursor_x = self._cursor_pos[1]
            self._text_changed = True
        elif event.character == "Enter":
            if self.multiline:
                line = self._cursor_pos[0]
                self._text.insert(line+1, self._text[line][self._cursor_pos[1]:])
                self._text[line] = self._text[line][:self._cursor_pos[1]]
                self._cursor_pos[0] += 1
                self._cursor_pos[1] = 0
                self._desired_cursor_x = self._cursor_pos[1]
                self._text_changed = True
            else:
                self.accept = event
        elif event.character == "Escape":
            self.cancel = event

        event.handled = True
        self.invalidate_draw()
        self.request_redraw()

    #------------------------------------------------------------------------
    # Component interface
    #------------------------------------------------------------------------

    def _draw_mainlayer(self, gc, view_bounds=None, mode="default"):
        gc.save_state()

        # Draw the text
        gc.set_font(self._style.font)
        gc.set_fill_color(self._style.text_color)
        char_w, char_h = self.metrics.get_text_extent("T")[2:4]
        char_h += self._style.line_spacing
        lines = [ "".join(ln) for ln in self._draw_text ]
        for i, line in enumerate(lines):
            x = self.x + self._style.text_offset
            if i > 0:
                y_offset = (i+1) * char_h - self._style.line_spacing
            else:
                y_offset = char_h - self._style.line_spacing
            y = self.y2 - y_offset - self._style.text_offset

            # Show text at the same scale as the graphics context
            ctm = gc.get_ctm()
            if hasattr(ctm, "scale"):
                scale = gc.get_ctm().scale()
            elif hasattr(gc, "get_ctm_scale"):
                scale = gc.get_ctm_scale()
            else:
                raise RuntimeError("Unable to get scale from GC.")
            x *= scale
            y *= scale
            gc.show_text_at_point(line, x, y)


        if self._draw_cursor:
            j, i = self._cursor_pos
            j -= self.__draw_text_ystart
            i -= self.__draw_text_xstart
            #print "text:", self.text[j][:i]
            x_offset = self.metrics.get_text_extent(lines[j][:i])[2]
            y_offset = char_h * j
            y = self.y2 - y_offset - self._style.text_offset
            if not self.multiline:
                char_h -= float(self._style.line_spacing)*.5

            gc.set_line_width(self._style.cursor_width)
            gc.set_stroke_color(self._style.cursor_color)
            gc.begin_path()
            x_position = self.x + x_offset + (char_w * .5)
            gc.move_to(x_position, y)
            gc.line_to(x_position, y - char_h)

            gc.stroke_path()

        gc.restore_state()


    #------------------------------------------------------------------------
    # TextField interface
    #------------------------------------------------------------------------

    def reset(self):
        """ Resets the text field. This involes reseting cursor position, text
            position, etc.
        """
        self._cursor_pos = [ 0, 0 ]
        self._old_cursor_pos = [ 0, 0 ]
        self.__draw_text = [ [] ]

    def _scroll_horz(self, num):
        """ Horizontally scrolls all the text that is being drawn by 'num' 
            characters. If num is negative, scrolls left. If num is positive,
            scrolls right.
        """
        self.__draw_text_xstart += num
        self._realign_horz()

    def _realign_horz(self):
        """ Realign all the text being drawn such that the first character being
            drawn in each line is the one at index '__draw_text_xstart.'
        """
        for i in xrange(len(self.__draw_text)):
            line = self._text[self.__draw_text_ystart + i]
            self.__draw_text[i] = self._clip_line(line, self.__draw_text_xstart)

    def _scroll_vert(self, num):
        """ Vertically scrolls all the text that is being drawn by 'num' lines.
            If num is negative, scrolls up. If num is positive, scrolls down.
        """
        x, y = self.__draw_text_xstart, self.__draw_text_ystart
        if num < 0:
            self.__draw_text = self.__draw_text[:num]
            lines = [ self._clip_line(line, x) for line in self._text[y+num:y] ]
            self.__draw_text = lines + self.__draw_text
        elif num > 0:
            self.__draw_text = self.__draw_text[num:]
            y += self._text_height
            lines = [ self._clip_line(line, x) for line in self._text[y:y+num] ]
            self.__draw_text.extend(lines)
        self.__draw_text_ystart += num

    def _clip_line(self, text, index, start=True):
        """ Return 'text' clipped beginning at 'index' if 'start' is True or
            ending at 'index' if 'start' is False.
        """
        box_width = self.width - self._style.text_offset
        total_width = 0.
        end_index = 1
        for t in text:
            w, h = self.metrics.get_text_extent(t)[2:4]
            total_width = total_width + w
            if total_width <= box_width:
                end_index = end_index + 1
            else:
                break
            
        if start:
            return text[index:min(index+end_index-1, len(text))]
        else:
            return text[max(0, index-end_index):index]

    def _refresh_viewed_line(self, line):
        """ Updates the appropriate line in __draw_text with the text at 'line'.
        """
        new_text = self._clip_line(self._text[line], self.__draw_text_xstart)
        index = line - self.__draw_text_ystart
        if index == len(self.__draw_text):
            self.__draw_text.append(new_text)
        else:
            self.__draw_text[index] = new_text

    def _acquire_focus(self, window):
        self._draw_cursor = True
        window.focus_owner = self
        window.on_trait_change(self._focus_owner_changed, "focus_owner")
        self.request_redraw()

    def _focus_owner_changed(self, obj, name, old, new):
        if old == self and new != self:
            obj.on_trait_change(self._focus_owner_changed, "focus_owner",
                                   remove=True)
        self._draw_cursor = False
        self.request_redraw()

    #------------------------------------------------------------------------
    # Property getters/setters and trait event handlers
    #------------------------------------------------------------------------

    def _get_text(self):
        return "\n".join([ "".join(line) for line in self._text ])

    def _set_text(self, val):
        if val == "":
            self._text = [ [] ]
        else:
            self._text = [ list(line) for line in val.splitlines() ]
        self.reset()        
        self.request_redraw()

    def _get__draw_text(self):
        # Rebuilding from scratch
        if self.__draw_text == [ [] ]:
            if self.multiline:
                self.__draw_text = []
                self.__draw_text_xstart, self.__draw_text_ystart = 0, 0
                end = min(len(self._text), self._text_height)
                for i in xrange(self.__draw_text_ystart, end):
                    line = self._clip_line(self._text[i], 0)
                    self.__draw_text.append(line)
            else:
                self.__draw_text = [ self._clip_line(self._text[0], 0) ]

        # Updating only the things that need updating
        else:
            # Scroll if necessary depending on where cursor moved
            # Adjust up
            if self._cursor_pos[0] < self.__draw_text_ystart:
                self._scroll_vert(-1)
            
            # Adjust down
            elif (self._cursor_pos[0] - self.__draw_text_ystart >= 
                  self._text_height):
                self._scroll_vert(1)

            # Adjust left
            line = self._text[self._cursor_pos[0]]
            chars_before_start = len(line[:self.__draw_text_xstart])
            chars_after_start = len(line[self.__draw_text_xstart:])
            if self._cursor_pos[1] < self.__draw_text_xstart:
                if chars_before_start <= self._text_width:
                    self.__draw_text_xstart = 0
                    self._realign_horz()
                else:
                    self._scroll_horz(-self._text_width)
            if (self.__draw_text_xstart > 0 and 
                chars_after_start+1 < self._text_width):
                self._scroll_horz(-1)
                
            # Adjust right
            num_chars = self._cursor_pos[1] - self.__draw_text_xstart
            if num_chars >= self._text_width:
                self._scroll_horz(num_chars - self._text_width + 1)
            
            # Replace text at cursor location
            if self._old_cursor_pos[0] < self._cursor_pos[0]:
                # A line has been created by an enter event
                self._refresh_viewed_line(self._old_cursor_pos[0])
            self._refresh_viewed_line(self._cursor_pos[0])
            
        return self.__draw_text

    def _get__text_width(self):
        if self._width_cache is None:
            char_width = self.metrics.get_text_extent("T")[2]
            self._width_cache = int(floor(self.width/char_width))
        return self._width_cache

    def _get__text_height(self):
        if self.multiline:
            if self._height_cache is None:
                char_height = self.metrics.get_text_extent("T")[3]
                height = self.height - 2*self._style.text_offset
                line_height = char_height + self._style.line_spacing
                self._height_cache = int(floor(height / line_height))
            return self._height_cache
        else:
            return 1

    def _container_changed(self, old, new):
        super(TextField, self)._container_changed(old, new)
        if hasattr(self.container, 'style_manager'):
            self._style = self.container.style_manager.text_field_style

    def __style_changed(self):
        """ Bg/border color is inherited from the style, so update it when the
            style changes. The height of a line also depends on style.
        """
        self.bgcolor = self._style.bgcolor
        self.border_visible = self._style.border_visible
        self.border_color = self._style.border_color
        
        self.metrics.set_font(self._style.font)
        if not self.multiline:
            self.height = (self.metrics.get_text_extent("T")[3] + 
                           self._style.text_offset*2)

        self.request_redraw()
