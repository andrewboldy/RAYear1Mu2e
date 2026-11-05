#!/usr/bin/env python3
"""
DumpARTTrees.py

Purpose
-------
This PyROOT program opens one Mu2e .art file and documents every TTree stored
in its ROOT-file hierarchy.  It writes one plain-text report per TTree.  Each
report records the selected TTree metadata, every branch and sub-branch, and
the leaves owned by each branch.

ROOT stores total entry counts on TBranches.  TLeaves describe values within
an entry and do not hold independent all-event entry counters, so leaf lines
report the entry count of their owning branch.

Output Naming
-------------
For an input file named dts.example.art, the usual ART TTrees produce:

    TxtOutputs/TTreeDumps/dts.example_Events_tree_structure.txt
    TxtOutputs/TTreeDumps/dts.example_SubRuns_tree_structure.txt
    TxtOutputs/TTreeDumps/dts.example_Runs_tree_structure.txt

The program creates TxtOutputs/TTreeDumps below the analysis directory from
which it is run.  The final console output identifies each tree as, for
example, "TTree 2 of 3" so its place in the .art structure is clear.

Typical Usage
-------------
After setting up the Mu2e/ROOT environment in the same gpvm terminal, run:

    python DumpARTTrees.py dts.example.art

The file must be readable by PyROOT.  Raw Mu2e .art payload interpretation may
require Mu2e dictionaries, but listing TTree structure uses ROOT metadata.
"""

# =============================================================================
# Standard Python Inclusions
# =============================================================================

import argparse
import os
import re
import sys
from typing import List, Tuple


# =============================================================================
# CERN ROOT / PyROOT Inclusions
# =============================================================================

try:
    import ROOT
except ImportError as import_error:
    print("ERROR: PyROOT could not be imported.")
    print("Run this program from a terminal with the Mu2e/ROOT environment set up.")
    print("Original import error: " + str(import_error))
    sys.exit(1)


# =============================================================================
# Program Constants
# =============================================================================

DIVIDER = "=" * 88
SUBDIVIDER = "-" * 88
DEFAULT_ANALYSIS_LEVEL = "art"


# =============================================================================
# Command-Line and Output-Name Helpers
# =============================================================================

def build_argument_parser() -> argparse.ArgumentParser:
    """Create the one-input-file command-line interface for this program."""

    # argparse supplies clear --help output before ROOT is opened.
    parser = argparse.ArgumentParser(
        description="Write one branch-and-leaf report for every TTree in a Mu2e .art file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python DumpARTTrees.py dts.example.art",
    )
    parser.add_argument(
        "input_art_file",
        help="Mu2e .art file whose complete TTree structure will be documented.",
    )
    parser.add_argument(
        "--analysis-level",
        default=DEFAULT_ANALYSIS_LEVEL,
        help="Console-summary label.  Default: " + DEFAULT_ANALYSIS_LEVEL,
    )
    return parser


def safe_tree_name(tree_name: str) -> str:
    """Convert a TTree name into a filename-safe suffix.

    Standard Mu2e tree names such as Events, SubRuns, and Runs are unchanged.
    Replacing other characters prevents a path separator or shell-special
    character in an unusual TTree name from changing the output destination.
    """

    return re.sub(r"[^A-Za-z0-9._-]+", "_", tree_name).strip("._") or "unnamed_tree"


def default_output_name(input_art_file: str, tree_name: str) -> str:
    """Build the run-directory-relative output path for one discovered TTree."""

    # Keep the complete .art filename stem so dumps from different input files
    # remain distinct.  splitext removes the final suffix, normally .art.
    input_base_name = os.path.basename(input_art_file)
    input_stem, _ = os.path.splitext(input_base_name)
    if not input_stem:
        raise RuntimeError("Could not derive an output name from the input file.")

    # The launch directory is the analysis directory on the gpvm.  Do not use
    # __file__, which would incorrectly tie output to the code's location.
    output_directory = os.path.join("TxtOutputs", "TTreeDumps")
    output_file_name = input_stem + "_" + safe_tree_name(tree_name) + "_tree_structure.txt"
    return os.path.join(output_directory, output_file_name)


# =============================================================================
# ROOT TTree Discovery
# =============================================================================

def find_trees(root_directory, directory_path: str = "") -> List[Tuple[str, object]]:
    """Recursively return every TTree as its ROOT path and live ROOT object."""

    # A ROOT directory contains TKeys.  Each key must be materialized with
    # ReadObj() before its ROOT inheritance can be identified.
    discovered_trees = []
    key_list = root_directory.GetListOfKeys()
    if not key_list:
        return discovered_trees

    for key in key_list:
        object_name = key.GetName()
        object_path = object_name if not directory_path else directory_path + "/" + object_name
        root_object = key.ReadObj()

        if root_object.InheritsFrom("TTree"):
            # Keep both a human-readable path and the object needed below to
            # access metadata, branches, sub-branches, and leaves.
            discovered_trees.append((object_path, root_object))
        elif root_object.InheritsFrom("TDirectory"):
            # Continue into nested ROOT directories so the program documents
            # all TTrees, not only those stored at the top file level.
            discovered_trees.extend(find_trees(root_object, object_path))

    return discovered_trees


# =============================================================================
# Branch and Leaf Report Builders
# =============================================================================

def append_leaf_lines(report_lines: List[str], branch, indent: str) -> int:
    """Append this branch's leaves and return how many leaf lines were written."""

    leaf_count = 0
    leaf_list = branch.GetListOfLeaves()
    if not leaf_list:
        return leaf_count

    for leaf in leaf_list:
        leaf_count += 1

        # A leaf's branch is the authoritative source for the all-event count.
        # The fallback handles unusual ROOT layouts where GetBranch() is null.
        owning_branch = leaf.GetBranch()
        leaf_entries = owning_branch.GetEntries() if owning_branch else branch.GetEntries()

        # Leaf type and static length define one stored value.  If a separate
        # count leaf controls variable length, include that relationship too.
        variable_length_note = ""
        leaf_count_object = leaf.GetLeafCount()
        if leaf_count_object:
            variable_length_note = ", variable length controlled by " + leaf_count_object.GetName()

        report_lines.append(
            indent
            + "Leaf: " + leaf.GetName()
            + " | Type: " + leaf.GetTypeName()
            + " | Entries (owning branch): " + str(leaf_entries)
            + " | Static length: " + str(leaf.GetLenStatic())
            + variable_length_note
        )

    return leaf_count


def append_branch_lines(
    report_lines: List[str], branch, branch_index: List[int], indent: str = ""
) -> Tuple[int, int]:
    """Append a branch and every descendant sub-branch recursively.

    branch_index is a one-element list so the same sequential branch counter
    is shared by every recursive call; Python integers cannot be updated by
    reference directly.
    """

    branch_index[0] += 1
    this_branch_number = branch_index[0]
    branch_class_name = branch.GetClassName()

    report_lines.append(
        indent
        + "Branch " + str(this_branch_number)
        + ": " + branch.GetName()
        + " | Entries: " + str(branch.GetEntries())
        + " | Class: "
        + (branch_class_name if branch_class_name else "(primitive/split branch)")
    )

    # ROOT branch titles frequently retain useful leaf-list information.
    if branch.GetTitle():
        report_lines.append(indent + "  Title: " + branch.GetTitle())

    total_branches = 1
    total_leaves = append_leaf_lines(report_lines, branch, indent + "  ")

    # Split object branches can own nested branches.  Print descendants under
    # their parent with additional indentation, preserving ROOT's hierarchy.
    sub_branch_list = branch.GetListOfBranches()
    if sub_branch_list and sub_branch_list.GetEntries() > 0:
        report_lines.append(indent + "  Sub-branches:")
        for sub_branch in sub_branch_list:
            sub_branch_total, sub_leaf_total = append_branch_lines(
                report_lines, sub_branch, branch_index, indent + "    "
            )
            total_branches += sub_branch_total
            total_leaves += sub_leaf_total

    return total_branches, total_leaves


def build_tree_report(tree_path: str, tree, tree_number: int, total_trees: int) -> Tuple[List[str], int, int]:
    """Build the complete text report for one TTree in the .art structure."""

    # Every individual file identifies its tree's sequence position so reports
    # remain interpretable even when opened separately from their siblings.
    report_lines = [
        DIVIDER,
        "Mu2e .art TTree Structure Report",
        DIVIDER,
        "TTree number: " + str(tree_number) + " of " + str(total_trees),
        "TTree path: " + tree_path,
        "TTree name: " + tree.GetName(),
        "TTree title: " + tree.GetTitle(),
        "TTree entries: " + str(tree.GetEntries()),
        SUBDIVIDER,
        "Branch and Leaf Structure",
        SUBDIVIDER,
    ]

    top_level_branches = tree.GetListOfBranches()
    if not top_level_branches or top_level_branches.GetEntries() == 0:
        report_lines.append("No branches were found in this TTree.")
        return report_lines, 0, 0

    # Start at one rather than zero in the user-facing report, and maintain a
    # continuous count through all recursively discovered sub-branches.
    branch_index = [0]
    total_branches = 0
    total_leaves = 0
    for branch in top_level_branches:
        branch_total, leaf_total = append_branch_lines(report_lines, branch, branch_index)
        total_branches += branch_total
        total_leaves += leaf_total

    report_lines.extend(
        [
            SUBDIVIDER,
            "Report Totals",
            "Top-level branches: " + str(top_level_branches.GetEntries()),
            "Total branches (including sub-branches): " + str(total_branches),
            "Total leaves: " + str(total_leaves),
            DIVIDER,
        ]
    )
    return report_lines, total_branches, total_leaves


def write_report(output_text_file: str, report_lines: List[str]) -> None:
    """Create the output directory when necessary and write one fresh report."""

    output_directory = os.path.dirname(os.path.abspath(output_text_file))
    if output_directory and not os.path.isdir(output_directory):
        # First use on a gpvm should not require manually making the output
        # folder.  exist_ok=True is also safe if another process made it first.
        os.makedirs(output_directory, exist_ok=True)

    # Write mode replaces a prior report for this exact input/tree pair; it
    # never appends a new dump to older, potentially incompatible contents.
    with open(output_text_file, "w", encoding="utf-8") as output_stream:
        output_stream.write("\n".join(report_lines) + "\n")


# =============================================================================
# Main Program
# =============================================================================

def main() -> int:
    """Open the .art file, report every discovered TTree, then close the file."""

    arguments = build_argument_parser().parse_args()

    # 1. Fail before opening ROOT when the input path cannot be found.
    if not os.path.isfile(arguments.input_art_file):
        print("ERROR: input .art file does not exist: " + arguments.input_art_file)
        return 1

    # 2. This is a metadata-only command-line utility, so suppress ROOT GUI
    # windows while it discovers TTrees and retrieves branch descriptions.
    ROOT.gROOT.SetBatch(True)
    input_file = ROOT.TFile.Open(arguments.input_art_file, "READ")
    if not input_file or input_file.IsZombie():
        print("ERROR: could not open input file: " + arguments.input_art_file)
        return 1

    try:
        # 3. Find every TTree once, before writing files, so each report can
        # state its stable number and the complete total for this .art file.
        discovered_trees = find_trees(input_file)
        if not discovered_trees:
            raise RuntimeError("No TTrees were found in the input .art file.")

        total_trees = len(discovered_trees)
        written_output_paths = set()

        # 4. Build and save an independent report for each discovered TTree.
        for tree_number, (tree_path, tree) in enumerate(discovered_trees, start=1):
            report_lines, branch_total, leaf_total = build_tree_report(
                tree_path, tree, tree_number, total_trees
            )
            output_text_file = default_output_name(arguments.input_art_file, tree.GetName())
            absolute_output_path = os.path.abspath(output_text_file)

            # Same-named TTrees in different directories would otherwise map
            # to one filename.  Refuse that overwrite and show the path.
            if absolute_output_path in written_output_paths:
                raise RuntimeError(
                    "Two discovered TTrees would write the same report name: "
                    + absolute_output_path + "\nConflicting TTree path: " + tree_path
                )

            write_report(output_text_file, report_lines)
            written_output_paths.add(absolute_output_path)

            # 5. State the tree's place in the .art structure and summarize
            # exactly which per-tree report was just produced.
            print(DIVIDER)
            print("Mu2e .art TTree Dump")
            print("TTree number: " + str(tree_number) + " of " + str(total_trees))
            print("TTree path: " + tree_path)
            print("TTree name: " + tree.GetName())
            print("Branch number: " + str(branch_total))
            print("Leaf number: " + str(leaf_total))
            print("Level of analysis structure: " + arguments.analysis_level)
            print("Saved text report: " + absolute_output_path)
            print(DIVIDER)

        print("Completed reports for " + str(total_trees) + " of " + str(total_trees) + " TTrees.")

    except RuntimeError as runtime_error:
        # Present expected discovery/naming failures without an internal trace.
        print("ERROR: " + str(runtime_error))
        return 1
    finally:
        # Close the input file even if one TTree could not be reported, which
        # avoids leaving ROOT file handles open in interactive Python sessions.
        input_file.Close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

