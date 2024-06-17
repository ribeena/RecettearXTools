# Recettear X-File to USD and Back converter

These scripts will parse the x-files to usd, and a Blender 4.1 usd exported
file back to .x for use in Recettear.

**Editted graphics**
![Screenshot of Recettear with hi-poly models.](/imgs/Editted.png)

**Original graphics**
![Screenshot of Recettear with original models.](/imgs/Default.png)

Widescreen screenshots are courtesy of https://github.com/just-harry/FancyScreenPatchForRecettear

Note: The tool doesn't currently support animation - there's some starting
code but not currently working

## Before Running

Requires Python and
```
  pip install usd-core
```

## Running the Script

You can run the script with a single filename argument:
```
  python main.py input_file.x
```
or
```
  python main.py modified_file.usd
```

You can also drag and drop .x or .usd files onto "Convert (drop file here).bat"

## Files made

When converting a .x file, it'll also create a `_speculars.json` file that stores specular
colours - this is a limitation of Blender 4.1's USD importer/exporter, so it'll
look up any specular colours for your frames/objects in there. Most files don't
seem to use specular colours however..

It'll also create a `_frames.json` file - if you change the name of any objects in
Blender, make sure to update this with the nickname. This file should be named
the same as your .usd file when you convert to a .x. You can also specify if the frames
need collision detection or not, and it'll change the identing format - at this
time I recommend pulling colliding items at the beginning of the world frame list.

## Blender tips

### Importing USD

Make sure all the listed images are in the same directory as your .usd file
you'll need to extract them using the Recettear extractor scripts:
https://github.com/UnrealPowerz/recettear-repacker

Import your USD, ensure that you merge all the ripped vertices
(press `m`, choose `by distance`)
you might want to set those as sharp edges, to help with normal generation.

You can also use the `merge_and_sharpen` script in Blender to speed up
this process.

### Exporting USD

When exporting choose the "World Frame" object (frame) and right click and
`select heirachy`, then in the export USD settings choose `selected`,
and turn off embed textures.

### Vertex Colours

Vertex colours are important to Recettear - they are essentially the ambient
lighting of the models. Under the shader in Blender, use a color attribute node
connected to an emission shader to help preview and paint the vertex colors.

![Vertex painting set up](/imgs/VertexColorSetup.png)

https://www.youtube.com/watch?v=pey5MQztvaY - is helpful in dealing with
Vertex colours.

### Better previews

The provided `blender_after_usd_import.py` you can drag into a script window
and run: it'll combine the vertex preview and make transparent green for you.

Note: this will mess up your USD export! it's for preview purposes only!

### Inverted faces

All the weird negative scaling etc means it's trial and error as to
which shapes need their normals flipped in Blender.

For "World Frame" it always seems to be scale -1,-1,-1, change to 1,1,-1.
Then use `Transform --> Apply Scale`. likewise, I recommend using
`Transform --> Apply Scale & Rotation` on the children, to limit the issues
but this may set the objects in the wrong position.

Don't forget in Viewport Shading mode, you can turn on `Backface Culling`
which should help get it right (provided you don't still have negative scales!).

## Preview .x files

https://www.cgdev.net/axe/download.php has a simple viewer which works well,
and shows normals if there are any issues with your models.

## Recettear's weird .x format

While this script does it best to parse the .x file, there's quite a few
challenges, still not fully sorted.

- vertex colours apply in a weird way, so are hard to preview in Blender
- the World_Frame FrameTransformMatrix seems to invert the size of things
  - you'll need to compensate for that in Blender
  - there's lots of weird negative scaling!
- there's heaps of excess materials etc, this seem to be fine stripped
- the indenting is not standard - correcting the indenting will disable
  the collision detection, but still work... some items use the .x file
  to make collisions, some don't