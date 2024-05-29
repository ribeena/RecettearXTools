import argparse
import os
from x_file_parser import XFileParser
from x_file_writer import USDToXConverter
from usd_exporter import USDExporter

def convert_x_to_usd(input_x_file, output_usd_file):
    parser = XFileParser(input_x_file)
    parser.parse()
    print('making usd')
    exporter = USDExporter(parser.frames, parser.materials, parser.animations)
    exporter.export(output_usd_file)

def convert_usd_to_x(input_file, output_x_file):
    converter = USDToXConverter(input_file)
    converter.convert(output_x_file)

def main(filename):
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext == '.x':
        output_usd_file = os.path.splitext(filename)[0] + '.usd'
        convert_x_to_usd(filename, output_usd_file)
        print(f"Converted {filename} to {output_usd_file}")

    elif file_ext == '.usd':
        output_x_file = os.path.splitext(filename)[0] + '.x'
        convert_usd_to_x(filename, output_x_file)
        print(f"Converted {filename} to {output_x_file}")

    else:
        raise ValueError("Unsupported file extension. Only .x and .usd files are supported.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert between .x and .usd files.")
    parser.add_argument("filename", help="Path to the .x or .usd file")
    args = parser.parse_args()
    main(args.filename)
