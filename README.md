iv -- Image Viewer
=========================

A simple image viewer that can recursively display images from directories in a
grid. Click on any image to display it full size.

Supports all image formats used on the web including animated GIFs and SVG.

Uses a browser engine (chromium) to do the rendering, so its format support
will always be current.

Dependencies
==============

python >= 3.5
PyQt >= 5.7
rapydscript-ng >= 0.7.8

Installation
==============

Simply clone this repository and run it using

```
python3 /path/to/cloned/repository /path/to/image/directory
```