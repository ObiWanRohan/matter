#!/usr/bin/python3

import sys
import os
import re
import argparse
import urllib.request as request
from urllib.error import HTTPError
from argparse import ArgumentParser, RawTextHelpFormatter
from os.path import dirname, basename, isdir, exists
from subprocess import run, check_call
from shutil import which, rmtree, copytree

# Configuration constants

MIN_PYTHON_VERSION = (3, 6)  # Mainly for f-strings

THEME_NAME = "Matter"
THEME_DESCRIPTION = (
    "Matter is a minimalist grub theme originally inspired by material design 2.\n"
    "Running this script without arguments will install the theme."
)
THEME_DEFAULT_HIGHLIGHT = "pink"
THEME_DEFAULT_FOREGROUND = "white-350"
THEME_DEFAULT_BACKGROUND = "bluegrey-900"
THEME_DEFAULT_FONT = "googlesans"
THEME_DEFAULT_FONT_SIZE = 32

INSTALLER_NAME = basename(__file__)

INSTALLER_DIR = dirname(os.path.realpath(INSTALLER_NAME))
INSTALLATION_SOURCE_DIR = f"{INSTALLER_DIR}/{THEME_NAME}"
INSTALLATION_TARGET_DIR = f"/boot/grub/themes/{THEME_NAME}"

GRUB_DEFAULTS_PATH = f"/etc/default/grub"
GRUB_CFG_PATH = f"/boot/grub/grub.cfg"
GRUB_MKCONFIG_PATH = which("grub-mkconfig")

THEME_TEMPLATE_PATH = f"{INSTALLER_DIR}/theme.txt.template"
GRUB_DEFAULTS_TEMPLATE_PATH = f"{INSTALLER_DIR}/grub.template"

THEME_OVERRIDES_TITLE = f"{THEME_NAME} Theme Overrides"
BEGIN_THEME_OVERRIDES = f"### BEGIN {THEME_OVERRIDES_TITLE}"
END_THEME_OVERRIDES = f"### END {THEME_OVERRIDES_TITLE}"

ICON_SVG_PATHF = f"{INSTALLER_DIR}/icons/{{}}.svg"
ICON_PNG_PATHF = f"{INSTALLATION_SOURCE_DIR}/icons/{{}}.png"

PALETTE = {
    "red": "#f44336",
    "pink": "#e91e63",
    "purple": "#9c27b0",
    "deeppurple": "#673ab7",
    "indigo": "#3f51b5",
    "blue": "#2196f3",
    "lightblue": "#03a9f4",
    "cyan": "#00bcd4",
    "teal": "#009688",
    "green": "#4caf50",
    "lightgreen": "#8bc34a",
    "lime": "#cddc39",
    "yellow": "#ffeb3b",
    "amber": "#ffc107",
    "orange": "#ff9800",
    "deeporange": "#ff5722",
    "brown": "#795548",
    "grey": "#9e9e9e",
    "bluegrey": "#607d8b",
    "white": "#ffffff",
    "black": "#000000",
    # Custom default colors
    "white-350": "#9E9E9E",
    "bluegrey-900": "#263238",
}
# Get available fonts from fonts/*.ttf by removing .ttf extension
AVAILABLE_FONTS = [
    filename[:-4]  # Remove .ttf
    for filename in os.listdir(f"{INSTALLER_DIR}/fonts/")
    if filename.endswith(".ttf")
]
AVAILABLE_COLORS = list(PALETTE.keys())

MDI_CDN = "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg/"

# Global user arguments set in main()
user_args: argparse.Namespace

# Utils


def sh(command):
    "Executes command in shell and returns its exit status"
    return run(command, shell=True).returncode


def shout(command):
    "Executes command in shell and returns its stdout"
    return run(command, shell=True).stdout


def has_command(command):
    return which(command) is not None


def check_python_version():
    installed = (sys.version_info.major, sys.version_info.minor)
    required = MIN_PYTHON_VERSION
    if installed < required:
        raise Exception(
            f"[Matter Error] Python {required[0]}.{required[1]} or later required."
        )


def check_root_or_prompt():
    if os.geteuid() != 0:
        print(f"[Matter Info] Request root access.")
        exit_code = sh("sudo -v")
        if exit_code != 0:
            raise Exception(
                "[Matter Error] Could not verify root access, you could try with sudo."
            )
        # Relaunch the program with sudo
        args = " ".join(sys.argv[1:])
        child_exit_code = sh(f"sudo {INSTALLER_DIR}/{INSTALLER_NAME} {args}")
        exit(child_exit_code)  # Propagate exit code


def delete_dir(directory):
    if isdir(directory):
        rmtree(directory)


def read_cleaned_grub_defaults():
    # Read previous defaults
    with open(GRUB_DEFAULTS_PATH, "r", newline="") as f:
        grub_defaults = f.read()

    # Remove previous theme defaults
    cleaned_grub_defaults = re.sub(
        f"\n*{BEGIN_THEME_OVERRIDES}.*{END_THEME_OVERRIDES}\n*",
        "",
        grub_defaults,
        flags=re.DOTALL,
    )
    return cleaned_grub_defaults


def read_cleaned_grub_mkconfig():
    assert (
        GRUB_MKCONFIG_PATH is not None
    ), "grub-mkconfig command is not present in your system"

    # Read previous defaults
    with open(GRUB_MKCONFIG_PATH, "r", newline="") as f:
        grub_mkconfig = f.read()

    # Remove previous theme defaults
    cleaned_grub_mkconfig = re.sub(
        f"\n*{BEGIN_THEME_OVERRIDES}.*{END_THEME_OVERRIDES}\n*",
        "",
        grub_mkconfig,
        flags=re.DOTALL,
    )
    return cleaned_grub_mkconfig


def download_icon(icon_name):
    print(f"[Matter Info] Download {icon_name}.svg")
    url = f"{MDI_CDN}{icon_name}.svg"
    try:
        with request.urlopen(url) as f:
            response = f.read()
    except HTTPError as err:
        print(f"[Matter Error] Couldn't get icon {icon_name} ({err.reason})")
        print(f"[Matter Error] At URL {err.geturl()}")
        exit(1)
    svg_path = ICON_SVG_PATHF.format(icon_name)
    with open(svg_path, "wb") as f:
        f.write(response)
    return svg_path


def get_downloaded_icons():
    return [
        filename[:-4]  # Remove .png
        for filename in os.listdir(f"{INSTALLATION_SOURCE_DIR}/icons/")
        if filename.endswith(".png")
    ]


def is_icon_downloaded(icon_name):
    svg_path = ICON_SVG_PATHF.format(icon_name)
    return exists(svg_path)


def convert_icon_svg2png(icon_name):
    if not has_command("convert"):
        print(
            "[Matter Error] Stop. The convert command from imagemagick was not found."
        )
        exit(1)
    if not has_command("inkscape"):
        print(
            "[Matter Warning] Resulting icons could look a bit off, consider installing inkscape"
        )
    src_path = ICON_SVG_PATHF.format(icon_name)
    dst_path = ICON_PNG_PATHF.format(icon_name)
    command = (
        r"convert -trim -scale 36x36 -extent 72x72 -gravity center "
        r"-define png:color-type=6 -background none -colorspace sRGB -channel RGB "
        r"-threshold -1 -density 300 -fill \#FFFFFF +opaque none "  # TODO: Editable color
        rf"{src_path} {dst_path}"
    )
    exit_code = sh(command)
    if exit_code != 0:
        print("[Matter Error] Stop. The convert command returned an error.")
        exit(1)


def parse_color(color_string):
    if color_string in AVAILABLE_COLORS:
        color = PALETTE[color_string]
    elif re.match(r"\#[0-9A-Fa-f]{6}", color_string) is not None:
        color = color_string
    else:
        print(f"[Matter Error] Invalid color parsed from {color_string}")
        print(
            f"[Matter Error] Color must be an escaped hex code like \\\\#C00FFE or one of: {AVAILABLE_COLORS}."
        )
        exit(1)
    return color


def check_icon_downloaded(icon):
    available_icons = get_downloaded_icons()
    if icon not in available_icons + ["_"]:
        print(f"[Matter Error] Invalid icon name: {icon}.")
        print(f"[Matter Error] Icons present are: {available_icons}.")
        exit(1)
    return icon


def check_font(font):
    if font not in AVAILABLE_FONTS:
        print(f"[Matter Error] Invalid font name: {font}.")
        print(f"[Matter Error] Font name must be one of: {AVAILABLE_FONTS}.")
        exit(1)
    return font


# Procedures


def clean_install_dir():
    print("[Matter Info] Clean install directory.")
    if isdir(INSTALLATION_TARGET_DIR):
        rmtree(INSTALLATION_TARGET_DIR)


def prepare_source_dir():
    print("[Matter Info] Build theme from user preferences.")

    # Get user color preferences
    highlight = parse_color(user_args.highlight)
    foreground = parse_color(user_args.foreground)
    background = parse_color(user_args.background)
    font = check_font(user_args.font)
    fontfile = user_args.fontfile
    fontsize = user_args.fontsize
    icons = user_args.icons

    # Prepare Icons

    # Do icon count match grub entry count?
    # Read entries from grub.cfg
    with open(GRUB_CFG_PATH, "r", newline="") as f:
        grub_cfg = f.read()

    entries = get_entry_names(grub_cfg)
    if len(icons) != len(entries):
        print(
            f"[Matter Error] You must specify {len(entries)} "
            f"icons ({len(icons)} provided) for entries:"
        )
        for i, m in enumerate(entries):
            print(f"{i + 1}. {m['entryname']}")
        exit(1)

    # Download not-yet-downloaded icons
    for icon in icons:
        if not is_icon_downloaded(icon) and icon != "_":
            download_icon(icon)

    # Convert icons
    for icon in icons:
        if icon != "_":
            convert_icon_svg2png(icon)

    # Prepare Font

    # Generate font file
    print("[Matter Info] Build font")
    grub_mkfont = "grub-mkfont"
    assert has_command(grub_mkfont), f"{grub_mkfont} command not found in your system"
    if fontfile is None:  # User did not specify custom font file
        fontfile = f"{INSTALLER_DIR}/fonts/{font}.ttf"
    stdout = shout(
        f"{grub_mkfont} -o {INSTALLATION_SOURCE_DIR}/font.pf2 {fontfile} -s {fontsize}"
    )
    if stdout:
        print(f"[Matter Error] {grub_mkfont} execution was not clean")
        print(f"[Matter Error] for fontfile: {fontfile}")
        exit(1)

    # Prepare Theme.txt

    # Parse theme template with user preferences
    with open(THEME_TEMPLATE_PATH, "r", newline="") as f:
        template = f.read()

    context = {
        "theme_name": THEME_NAME,
        "highlight": highlight,
        "foreground": foreground,
        "background": background,
    }
    parsed_theme = template.format(**context)

    theme_file_path = f"{INSTALLATION_SOURCE_DIR}/theme.txt"
    with open(theme_file_path, "w") as f:
        f.write(parsed_theme)


def prepare_target_dir():
    print("[Matter Info] Prepare installation directory.")
    clean_install_dir()


def copy_source_to_target():
    print("[Matter Info] Copy built theme to installation directory.")
    copytree(INSTALLATION_SOURCE_DIR, INSTALLATION_TARGET_DIR)


def update_grub_cfg():
    COMMAND = "update-grub"
    print(f"[Matter Info] Remake grub.cfg with {COMMAND}.")
    assert has_command(COMMAND), f"{COMMAND} command not found in your system"
    sh(COMMAND)


def update_grub_defaults():
    print(f"[Matter Info] Patch {GRUB_DEFAULTS_PATH} with {THEME_OVERRIDES_TITLE}.")
    grub_configs = read_cleaned_grub_defaults()

    # Parse grub defaults template, append parsed contents, and write back

    with open(GRUB_DEFAULTS_TEMPLATE_PATH, "r", newline="") as f:
        template = f.read()

    context = {"installation_dir": INSTALLATION_TARGET_DIR}
    parsed_extra_grub = template.format(**context)
    grub_configs += (
        f"\n\n{BEGIN_THEME_OVERRIDES}\n{parsed_extra_grub}\n{END_THEME_OVERRIDES}\n\n"
    )

    with open(GRUB_DEFAULTS_PATH, "w") as f:
        f.write(grub_configs)


def clean_grub_defaults():
    print(f"[Matter Info] Clean {THEME_OVERRIDES_TITLE} from {GRUB_DEFAULTS_PATH}.")
    cleaned_grub_defaults = read_cleaned_grub_defaults()
    with open(GRUB_DEFAULTS_PATH, "w") as f:
        f.write(cleaned_grub_defaults)


def clean_grub_mkconfig():
    print(f"[Matter Info] Clean {THEME_OVERRIDES_TITLE} from {GRUB_MKCONFIG_PATH}.")
    cleaned_grub_mkconfig = read_cleaned_grub_mkconfig()
    with open(GRUB_MKCONFIG_PATH, "w") as f:
        f.write(cleaned_grub_mkconfig)


def get_entry_names(grub_cfg):
    "Gets the entry names from grub.cfg contents"
    pattern = (
        r"(?P<head>(?:submenu|menuentry) ?)"  # menuentry or submenu
        r"(?:\"|')"  # " or '
        r"(?P<entryname>[^\"']*)"  # capture the entry name (without quotes)
        r"(?:\"|')"  # " or '
        r"(?P<tail>[^\{]*\{)"  # The rest of the entry header until a { is found
    )
    matchiter = re.finditer(pattern, grub_cfg)
    matches = list(matchiter)
    return matches


# Main procedures


def do_preinstall_hint():
    print(f"[Matter Info] Argument -i required. Which icons go to which grub entries?.")
    print(f"[Matter Info] Your grub entries are:")
    do_list_grub_cfg_entries()
    print(f"[Matter Info] Look for icons you like at https://materialdesignicons.com/")
    print(f'[Matter Info] Then install with (you can use "_" for an empty icon):')
    print(f"[Matter Info] ./matter.py -i icon-for-entry-1 icon-for-entry-2 ...")
    print(f"[Matter Info] Example (with 8 entries):")
    print(f"[Matter Info] ./matter.py -i ubuntu microsoft-windows folder _ _ _ _ cog")


def do_install():
    print(f"[Matter Info] Begin {THEME_NAME} install.")
    check_root_or_prompt()
    prepare_source_dir()
    prepare_target_dir()
    copy_source_to_target()
    update_grub_defaults()
    do_set_icons()
    update_grub_cfg()
    print(f"[Matter Info] {THEME_NAME} succesfully installed.")


def do_uninstall():
    print(f"[Matter Info] Begin {THEME_NAME} uninstall.")
    check_root_or_prompt()
    clean_grub_defaults()
    clean_grub_mkconfig()
    clean_install_dir()
    update_grub_cfg()
    print(f"[Matter Info] {THEME_NAME} succesfully uninstalled.")


def do_list_grub_cfg_entries():
    # Read current grub cfg
    with open(GRUB_CFG_PATH, "r", newline="") as f:
        grub_cfg = f.read()

    entries = get_entry_names(grub_cfg)

    for i, m in enumerate(entries):
        print(f"{i + 1}. {m['entryname']}")


def do_patch_grub_cfg_icons():
    print(f"[Matter Info] Begin {GRUB_CFG_PATH} patch.")
    icons = user_args.icons
    if icons is None:
        print(f"[Matter Error] Stop. Unspecified icons (--icons/-i argument).")
        exit(1)
    icons = [check_icon_downloaded(i) for i in icons]

    # Read current grub cfg
    with open(GRUB_CFG_PATH, "r", newline="") as f:
        grub_cfg = f.read()

    entries = get_entry_names(grub_cfg)
    if len(icons) != len(entries):
        print(
            f"[Matter Error] You must specify {len(entries)} "
            f"icons ({len(icons)} provided) for entries:"
        )
        for i, m in enumerate(entries):
            print(f"{i + 1}. {m['entryname']}")
        exit(1)

    # Build new grub cfg with given icons
    new_grub_cfg = ""
    next_seek = 0
    for m, i in zip(entries, icons):
        mstart, mend = m.span()
        new_grub_cfg += grub_cfg[next_seek:mstart]
        icon_class = f" --class {i} " if i != "_" else ""
        new_grub_cfg += f'{m["head"]}"{m["entryname"]}"{icon_class}{m["tail"]}'
        next_seek = mend
    new_grub_cfg += grub_cfg[mend:]

    # Write new grub cfg back
    check_root_or_prompt()
    with open(GRUB_CFG_PATH, "w") as f:
        f.write(new_grub_cfg)

    print(f"[Matter Info] {len(icons)} icons succesfully patched onto {GRUB_CFG_PATH}.")


def do_set_icons():
    # Patch grub.cfg
    do_patch_grub_cfg_icons()

    # Patch grub-mkconfig so everytime it executes, it patches grub.cfg
    print(f"[Matter Info] Begin {GRUB_MKCONFIG_PATH} patch.")
    print(f"[Matter Info] Clean old {GRUB_MKCONFIG_PATH} patch if any.")
    cmd_icons = " ".join(user_args.icons)
    seticons_call = f"{INSTALLER_DIR}/{INSTALLER_NAME} -so -i {cmd_icons} >&2"
    new_grub_mkconfig = read_cleaned_grub_mkconfig()
    new_grub_mkconfig += (
        f"\n\n{BEGIN_THEME_OVERRIDES}\n{seticons_call}\n{END_THEME_OVERRIDES}\n\n"
    )

    check_root_or_prompt()
    with open(GRUB_MKCONFIG_PATH, "w") as f:
        f.write(new_grub_mkconfig)

    print(
        f"[Matter Info] {GRUB_MKCONFIG_PATH} succesfully patched, icons should now persist between grub updates."
    )


# Script arguments


def parse_args():
    parser = ArgumentParser(
        description=THEME_DESCRIPTION,
        epilog=f"[Available colors] are: {', '.join(AVAILABLE_COLORS)}.\n"
        "You can specify your own hex colors as well (e.g. \\#C0FFEE, \\#FF00FF, etc).\n"
        f"[Available fonts] are: {', '.join(AVAILABLE_FONTS)}\n"
        "You can always specify your own with the -ff argument\n"
        f"[Available icons] can be found at https://materialdesignicons.com/\n"
        "For requests open an issue on:\n"
        "https://github.com/mateosss/matter/issues",
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "--listentries", "-l", action="store_true", help=f"list grub entries",
    )
    parser.add_argument(
        "--icons",
        "-i",
        type=str,
        nargs="*",
        help=f"specify icons for each grub entry listed with -l",
    )
    parser.add_argument(
        "--seticons",
        "-si",
        action="store_true",
        help=f"set grub entries icons given by -i and patch grub-mkconfig for persistence",
    )
    parser.add_argument(
        "--seticons_once",
        "-so",
        action="store_true",
        help=f"set grub entries icons given by -i, will be reverted on next grub update",
    )
    parser.add_argument(
        "--uninstall", "-u", action="store_true", help=f"uninstall {THEME_NAME}",
    )
    parser.add_argument(
        "--highlight",
        "-hl",
        type=str,
        help=f"selected text color",
        default=THEME_DEFAULT_HIGHLIGHT,
    )
    parser.add_argument(
        "--foreground",
        "-fg",
        type=str,
        help=f"main text color",
        default=THEME_DEFAULT_FOREGROUND,
    )
    parser.add_argument(
        "--background",
        "-bg",
        type=str,
        help=f"solid background color",
        default=THEME_DEFAULT_BACKGROUND,
    )
    parser.add_argument(
        "--font",
        "-f",
        type=str,
        help=f"theme font from prepackaged fonts",
        default=THEME_DEFAULT_FONT,
        choices=AVAILABLE_FONTS,
    )
    parser.add_argument(
        "--fontfile", "-ff", type=str, help=f"theme font from custom .ttf file"
    )
    parser.add_argument(
        "--fontsize",
        "-fs",
        type=int,
        help=f"theme font size",
        default=THEME_DEFAULT_FONT_SIZE,
    )
    return parser.parse_args()


if __name__ == "__main__":
    check_python_version()
    user_args = parse_args()

    if user_args.listentries:
        do_list_grub_cfg_entries()
    elif user_args.seticons_once:
        do_patch_grub_cfg_icons()
    elif user_args.seticons:
        do_set_icons()
    elif user_args.uninstall:
        do_uninstall()
    elif user_args.icons is None:
        do_preinstall_hint()
    else:
        do_install()
