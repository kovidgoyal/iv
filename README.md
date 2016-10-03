iv -- Image Viewer
=========================

A simple image viewer that can recursively display images from directories in a
grid. Click on any image to display it full size.

Supports all image formats used on the web including animated GIFs and SVG.

Uses a browser engine (chromium) to do the rendering, so its format support
will always be current.

Dependencies
==============

* python >= 3.5
* PyQt >= 5.7
* rapydscript-ng >= 0.7.9

Installation
==============

Simply clone this repository and run it using

```
python3 /path/to/cloned/repository /path/to/image/directory
```

Controls
===========

`iv` is largely keyboard controlled. The keyboard shortcuts in the two view
are:

Grid View
-------------

* `c` - Toggle the captions
* `+` - Increase thumbnail size
* `-` - Decrease thumbnail size

Single Image View
-------------------

* `c` - Toggle the information display
* `+` - Zoom in
* `-` - Zoom out
* `0` - Reset zoom to no zoom
