# Recettear X-File to USD and Back converter

These scripts will parse the x-files to usd, and a Blender 4.1 usd exported
file back to .x for use in Recettear.

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

When converting a .x file, it'll also create a .json file that stores specular
colours - this is a limitation of Blender 4.1's USD importer/exporter, so it'll
look up any specular colours for your frames/objects in there. Most files don't
seem to use specular.

## Blender tips

### Importing USD

Make sure all the listed images are in the same directory as your .usd file
you'll need to extract them using the Recettear extractor scripts:
https://github.com/UnrealPowerz/recettear-repacker

Import your USD, ensure that you merge all the ripped vertices
(press `m`, choose `by distance`)
you might want to set those as sharp edges, to help with normal generation.

### Exporting USD

When exporting choose the "None" object (frame) and right click and
`select heirachy`, then in the export USD settings choose `selected`,
and turn off embed textures.

### Vertex Colours

Vertex colours are important to Recettear - they are essentially the ambient
lighting of the models. Under the shader in Blender, use a color attribute node
connected to an emission shader to help preview and paint the vertex colors.

https://www.youtube.com/watch?v=pey5MQztvaY - is helpful in dealing with
Vertex colours.

## Better previews

The provided `blender_after_usd_import.py` you can drag into a script window
and run: it'll combine the vertex preview and make transparent green for you.

Note: this will mess up your USD export! it's for preview purposes only!

## Preview .x files

https://www.cgdev.net/axe/download.php has a simple viewer which works well,
and shows normals if there are any issues with your models.