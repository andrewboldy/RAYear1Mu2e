#!/usr/bin/env python3
"""
TreeBranchCompare.py

Purpose
-------
This PyROOT program compares the branch names in one named TTree from two
ROOT-compatible files, including Mu2e .art files.  It reports the total branch
count in each file and identifies branch names that appear only in the first
file or only in the second file.

The comparison intentionally uses names only.  It does not compare branch
entry counts, types, titles, or stored data because entry counts naturally
change when files contain different numbers of events.

Inputs
------
* First ROOT or .art file: the reference structure.
* Second ROOT or .art file: the structure being compared to the reference.
* TTree name or full ROOT path, such as Events or EventNtuple/ntuple.

Typical Usage
-------------
After setting up Mu2e/ROOT in the same terminal, run:

    python TreeBranchCompare.py first.art second.art Events

Interpretation
--------------
* "Only in first file" means the branch is present in the reference tree but
  absent from the second tree.  It was therefore subtracted in the second file.
* "Only in second file" means the branch is absent from the reference tree but
  present in the second tree.  It was therefore added in the second file.

For split object branches, this program recursively compares sub-branches as
well.  Their printed identifiers are hierarchy paths made only from branch
names, such as parent_branch/sub_branch.

Output
------
The same comparison shown in the terminal is saved below the directory from
which the program is run:

    TTreeCompare/<first-art-type>_VS_<second-art-type>_<tree-name>_branch_comparison.txt
"""

# =============================================================================
# Standard Python Inclusions
# =============================================================================

import argparse
import os
import re
import sys
from typing import List, Set, Tuple


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


# =============================================================================
# Command-Line Helpers
# =============================================================================

def build_argument_parser() -> argparse.ArgumentParser:
    """Create the required two-file and one-TTree command-line interface."""

    # argparse creates useful --help text and checks that all three required
    # positional arguments were supplied before ROOT files are opened.
    parser = argparse.ArgumentParser(
        description="Compare branch names for one TTree in two ROOT or .art files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python TreeBranchCompare.py first.art second.art Events\n\n"
            "The first file is the reference.  'Only in second file' branches "
            "are additions relative to that reference."
        ),
    )
    parser.add_argument(
        "first_input_file",
        help="Reference ROOT or .art file.",
    )
    parser.add_argument(
        "second_input_file",
        help="ROOT or .art file to compare against the reference.",
    )
    parser.add_argument(
        "tree_name",
        help="TTree name or full ROOT path to compare, for example Events.",
    )
    parser.add_argument(
        "--output",
        dest="output_text_file",
        default=None,
        help=(
            "Optional comparison-report path.  Default: TTreeCompare/"
            "<first-type>_VS_<second-type>_<tree-name>_branch_comparison.txt"
        ),
    )
    return parser


def safe_filename_part(name: str) -> str:
    """Replace filename-unsafe characters without changing comparison content."""

    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "unnamed"


def default_output_name(first_input_file: str, second_input_file: str, tree_name: str) -> str:
    """Build the run-directory-relative default report name for one comparison."""

    # The first three input-file characters identify the Mu2e data-structure
    # type in the requested convention: dts, dig, mcs, nts, and so on.
    first_type = os.path.basename(first_input_file)[:3]
    second_type = os.path.basename(second_input_file)[:3]
    if not first_type or not second_type:
        raise RuntimeError("Could not derive a comparison-report name from the input files.")

    # TTreeCompare is relative to the current analysis directory on the gpvm,
    # not to this script's source-code location.
    output_directory = "TTreeCompare"
    output_file_name = (
        safe_filename_part(first_type)
        + "_VS_"
        + safe_filename_part(second_type)
        + "_"
        + safe_filename_part(tree_name)
        + "_branch_comparison.txt"
    )
    return os.path.join(output_directory, output_file_name)


# =============================================================================
# ROOT TTree Discovery and Selection
# =============================================================================

def find_trees(root_directory, directory_path: str = "") -> List[Tuple[str, object]]:
    """Recursively return every TTree as its ROOT path and its ROOT object."""

    # ROOT directories contain TKeys.  A key must be read into an object before
    # ROOT can reveal whether it is a TTree or a nested directory.
    discovered_trees = []
    key_list = root_directory.GetListOfKeys()
    if not key_list:
        return discovered_trees

    for key in key_list:
        object_name = key.GetName()
        object_path = object_name if not directory_path else directory_path + "/" + object_name
        root_object = key.ReadObj()

        if root_object.InheritsFrom("TTree"):
            discovered_trees.append((object_path, root_object))
        elif root_object.InheritsFrom("TDirectory"):
            # Recurse because a tree can be stored below the top file level.
            discovered_trees.extend(find_trees(root_object, object_path))

    return discovered_trees


def select_tree(input_file, requested_tree_name: str, input_label: str):
    """Return one unambiguous TTree from an opened file.

    An exact ROOT path is preferred.  A bare name is accepted only if exactly
    one discovered TTree has that name, preventing a silent wrong comparison.
    """

    discovered_trees = find_trees(input_file)
    if not discovered_trees:
        raise RuntimeError("No TTrees were found in the " + input_label + " input file.")

    # Direct ROOT lookup supports a hierarchical request such as
    # EventNtuple/ntuple without requiring the user to know traversal details.
    requested_object = input_file.Get(requested_tree_name)
    if requested_object and requested_object.InheritsFrom("TTree"):
        return requested_tree_name, requested_object

    # If a short name was supplied, resolve it only when the result is unique.
    name_matches = [
        (tree_path, tree)
        for tree_path, tree in discovered_trees
        if tree.GetName() == requested_tree_name
    ]
    if len(name_matches) == 1:
        return name_matches[0]

    available_paths = "\n  ".join(tree_path for tree_path, _ in discovered_trees)
    raise RuntimeError(
        "Could not uniquely select TTree '" + requested_tree_name + "' in the "
        + input_label + " input file.\nAvailable TTree paths:\n  " + available_paths
    )


# =============================================================================
# Recursive Branch Collection
# =============================================================================

def collect_branch_names(branch, parent_path: str = "") -> Set[str]:
    """Return this branch's hierarchy paths, including all sub-branches.

    Branch objects may represent split C++ objects.  Comparing only the TTree
    top-level list would miss their descendants, so this function adds the
    current branch and recursively visits every nested branch.
    """

    # Build an identifier from names only.  The slash is a display hierarchy,
    # not a ROOT data lookup; no entry counts or other changing metadata enter
    # the comparison.
    branch_path = branch.GetName() if not parent_path else parent_path + "/" + branch.GetName()
    branch_names = {branch_path}

    sub_branch_list = branch.GetListOfBranches()
    if sub_branch_list and sub_branch_list.GetEntries() > 0:
        for sub_branch in sub_branch_list:
            branch_names.update(collect_branch_names(sub_branch, branch_path))

    return branch_names


def collect_tree_branch_names(tree) -> Set[str]:
    """Collect every top-level and nested branch name for one selected TTree."""

    branch_names = set()
    top_level_branches = tree.GetListOfBranches()
    if not top_level_branches:
        return branch_names

    for branch in top_level_branches:
        # Set.update removes duplicate names automatically while preserving the
        # complete branch hierarchy required for the comparison.
        branch_names.update(collect_branch_names(branch))

    return branch_names


# =============================================================================
# Console Report Helpers
# =============================================================================

def build_branch_list(heading: str, branch_names: Set[str]) -> List[str]:
    """Build a labeled, alphabetically ordered branch-difference list."""

    output_lines = [heading + ": " + str(len(branch_names))]
    if not branch_names:
        output_lines.append("  None")
        return output_lines

    for branch_name in sorted(branch_names):
        output_lines.append("  " + branch_name)

    return output_lines


def build_comparison_report(
    first_file: str,
    second_file: str,
    first_tree_path: str,
    second_tree_path: str,
    requested_tree_name: str,
    first_branch_names: Set[str],
    second_branch_names: Set[str],
) -> List[str]:
    """Build the complete branch-name-only comparison for console and file."""

    # Set subtraction deliberately ignores all common names.  What remains is
    # exactly the requested structural change: removed and added branches.
    only_in_first = first_branch_names - second_branch_names
    only_in_second = second_branch_names - first_branch_names

    report_lines = [
        DIVIDER,
        "TTree Branch Comparison",
        "Requested TTree name/path: " + requested_tree_name,
        "First file (reference): " + first_file,
        "First TTree path: " + first_tree_path,
        "First-file branch number: " + str(len(first_branch_names)),
        "Second file (comparison): " + second_file,
        "Second TTree path: " + second_tree_path,
        "Second-file branch number: " + str(len(second_branch_names)),
        DIVIDER,
    ]
    report_lines.extend(build_branch_list("Only in first file (subtracted in second file)", only_in_first))
    report_lines.extend(build_branch_list("Only in second file (added in second file)", only_in_second))

    if not only_in_first and not only_in_second:
        report_lines.append("Result: the selected TTrees have identical branch-name structure.")
    else:
        report_lines.append("Result: the selected TTrees differ in the branch names listed above.")

    report_lines.append(DIVIDER)
    return report_lines


def write_report(output_text_file: str, report_lines: List[str]) -> None:
    """Create TTreeCompare when needed and write the full comparison report."""

    output_directory = os.path.dirname(os.path.abspath(output_text_file))
    if output_directory and not os.path.isdir(output_directory):
        # First use should not require the analyst to create TTreeCompare by
        # hand.  exist_ok=True is harmless if it already exists.
        os.makedirs(output_directory, exist_ok=True)

    with open(output_text_file, "w", encoding="utf-8") as output_stream:
        output_stream.write("\n".join(report_lines) + "\n")


# =============================================================================
# Main Program
# =============================================================================

def main() -> int:
    """Validate files, select both TTrees, compare their branch names, and close."""

    arguments = build_argument_parser().parse_args()

    # 1. Validate both paths before PyROOT tries to open either file.
    for input_file_name, input_label in [
        (arguments.first_input_file, "first"),
        (arguments.second_input_file, "second"),
    ]:
        if not os.path.isfile(input_file_name):
            print("ERROR: " + input_label + " input file does not exist: " + input_file_name)
            return 1

    # 2. No graphics are required for metadata inspection, so keep ROOT in
    # batch mode while opening both files and traversing their TTrees.
    ROOT.gROOT.SetBatch(True)
    first_root_file = ROOT.TFile.Open(arguments.first_input_file, "READ")
    second_root_file = ROOT.TFile.Open(arguments.second_input_file, "READ")

    if not first_root_file or first_root_file.IsZombie():
        print("ERROR: could not open first input file: " + arguments.first_input_file)
        return 1
    if not second_root_file or second_root_file.IsZombie():
        print("ERROR: could not open second input file: " + arguments.second_input_file)
        first_root_file.Close()
        return 1

    try:
        # 3. Select the requested tree separately in each file.  The paths may
        # differ while the supplied short tree name still identifies both.
        first_tree_path, first_tree = select_tree(
            first_root_file, arguments.tree_name, "first"
        )
        second_tree_path, second_tree = select_tree(
            second_root_file, arguments.tree_name, "second"
        )

        # 4. Gather branch hierarchy names only.  GetEntries() is never read,
        # so files with different event counts compare structurally.
        first_branch_names = collect_tree_branch_names(first_tree)
        second_branch_names = collect_tree_branch_names(second_tree)

        # 5. Build one report once, then send identical structural results to
        # both the terminal and the requested TTreeCompare text file.
        report_lines = build_comparison_report(
            arguments.first_input_file,
            arguments.second_input_file,
            first_tree_path,
            second_tree_path,
            arguments.tree_name,
            first_branch_names,
            second_branch_names,
        )
        output_text_file = arguments.output_text_file
        if not output_text_file:
            output_text_file = default_output_name(
                arguments.first_input_file,
                arguments.second_input_file,
                arguments.tree_name,
            )

        write_report(output_text_file, report_lines)
        print("\n".join(report_lines))
        print("Saved comparison report: " + os.path.abspath(output_text_file))

    except RuntimeError as runtime_error:
        # Expected selection failures appear as a short terminal error rather
        # than an internal traceback, then the command signals failure.
        print("ERROR: " + str(runtime_error))
        return 1
    finally:
        # Both successful opens are explicitly closed regardless of comparison
        # outcome, which matters in long-lived interactive PyROOT sessions.
        first_root_file.Close()
        second_root_file.Close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

