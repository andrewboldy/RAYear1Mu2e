#!/usr/bin/env python3
"""
DumpROOTTree.py

Purpose
-------
This PyROOT program opens one ROOT file, selects one TTree, and writes a
readable tree-structure report to a plain-text file.  The report records the
selected TTree name, its number of entries, every branch (including nested
sub-branches), and the leaves owned by every branch.

For every branch and leaf, the report gives the associated entry count.  ROOT
stores this count on TBranches.  A TLeaf does not own an independent all-event
entry counter, so the leaf line reports the entry count of its owning branch.

Inputs
------
* One ROOT file containing exactly one TTree, or a tree selected explicitly
  with --tree.

Outputs
-------
* A plain-text report.  By default, it is named
  <complete_input_name_without_.root>_tree_structure.txt and stored in
  TxtOutputs/TTreeDumps below the directory from which this program is run.
* A concise console summary containing how the TTree was selected, the
  selected TTree name, the total number of branches, and the analysis-
  structure label.  The default label is "ntuple" because this program is
  intended for an ntuple-level inspection.

Typical Usage
-------------
Before running, set up the Mu2e/PyROOT environment in the same terminal.  For
example, use the Mu2e setup appropriate to the checkout, then run:

    python DumpROOTTree.py input.root

If the ROOT file contains more than one TTree, identify the desired tree by
its ROOT path or name:

    python DumpROOTTree.py input.root --tree EventNtuple/ntuple

Choose a custom text-file name or analysis-structure label when needed:

    python DumpROOTTree.py input.root --tree ntuple \
        --output ntuple_structure.txt --analysis-level ntuple

Notes
-----
* This program is intended for general ROOT TTrees and does not assume an
  EventNtuple/RooUtil schema.
* For raw Mu2e .art files, run from a ROOT/art-compatible Mu2e environment.
  The script can inspect the TTree layout, but interpreting product payloads
  may require the Mu2e dictionaries loaded by that environment.
"""

# =============================================================================
# Standard Python Inclusions
# =============================================================================

import argparse
import os
import sys
from typing import List, Optional, Tuple


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

DEFAULT_ANALYSIS_LEVEL = "ntuple"
DIVIDER = "=" * 88
SUBDIVIDER = "-" * 88


# =============================================================================
# Argument and File-Name Helpers
# =============================================================================

def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface used to select the file and TTree.

    Keeping argument definitions together makes it straightforward to see what
    a user may configure without reading the ROOT-processing code below.
    """

    # argparse produces the standard --help text and stops execution before
    # ROOT is opened if a required command-line value is missing or malformed.
    parser = argparse.ArgumentParser(
        description=(
            "Write a TTree branch-and-leaf structure report for one ROOT file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python DumpROOTTree.py input.root\n"
            "  python DumpROOTTree.py input.root --tree EventNtuple/ntuple\n"
            "  python DumpROOTTree.py input.root --output structure.txt"
        ),
    )

    # Positional argument: this is the one ROOT file to be inspected.
    parser.add_argument(
        "input_root_file",
        help="ROOT file containing the TTree to document.",
    )
    # Optional TTree selector: omitted only when the file contains one TTree.
    parser.add_argument(
        "--tree",
        dest="tree_name",
        default=None,
        help=(
            "TTree name or path.  This is required only when the input file "
            "contains more than one TTree."
        ),
    )
    # Optional output override: otherwise default_output_name() chooses the
    # standard TxtOutputs/TTreeDumps destination and descriptive filename.
    parser.add_argument(
        "--output",
        dest="output_text_file",
        default=None,
        help=(
            "Output report path.  Default: TxtOutputs/TTreeDumps/"
            "<complete_input_name_without_.root>_tree_structure.txt"
        ),
    )
    # This label does not change ROOT processing.  It documents the analysis
    # stage in the concise console message for the person running the script.
    parser.add_argument(
        "--analysis-level",
        default=DEFAULT_ANALYSIS_LEVEL,
        help=(
            "Label printed in the final console summary.  "
            "Default: " + DEFAULT_ANALYSIS_LEVEL
        ),
    )

    return parser


def default_output_name(input_root_file: str) -> str:
    """Return the requested run-directory-relative default report path.

    The full input basename is retained, except for its .root suffix.  For
    example, nts.some_dataset.root produces
    TxtOutputs/TTreeDumps/nts.some_dataset_tree_structure.txt.  Retaining the
    complete source name prevents reports from different ntuples overwriting
    one another.  TxtOutputs/TTreeDumps is deliberately relative to the
    directory from which the user launches this program, matching analysis
    folder use on a gpvm rather than a particular source-code checkout.
    """

    # Strip directories first because only the ROOT file's own name belongs in
    # the output name; then remove the final extension, normally .root.
    input_base_name = os.path.basename(input_root_file)
    input_stem, _ = os.path.splitext(input_base_name)

    if not input_stem:
        raise RuntimeError("Could not derive an output name from the input file.")

    # Do not derive this location from __file__.  The analysis folder where
    # the command is launched defines the desired output location on a gpvm.
    # os.path.join supplies the correct directory separator on the host system.
    output_directory = os.path.join("TxtOutputs", "TTreeDumps")

    return os.path.join(output_directory, input_stem + "_tree_structure.txt")


# =============================================================================
# ROOT TTree Discovery and Selection
# =============================================================================

def find_trees(root_directory, directory_path: str = "") -> List[Tuple[str, object]]:
    """Recursively find every TTree and return its full ROOT path and object.

    ROOT files can store TTrees inside directories.  Searching recursively keeps
    the program general while allowing the user to select a tree by a familiar
    path such as EventNtuple/ntuple.
    """

    # Each saved ROOT object has a TKey.  The key list is therefore the proper
    # place to start when inspecting a file or a nested ROOT directory.
    discovered_trees = []
    key_list = root_directory.GetListOfKeys()

    # An empty directory is valid; it simply contributes no TTrees to the
    # recursive search.
    if not key_list:
        return discovered_trees

    for key in key_list:
        # GetName() gives the object's local name.  Prepending directory_path
        # creates a user-selectable path such as EventNtuple/ntuple.
        object_name = key.GetName()
        object_path = object_name if not directory_path else directory_path + "/" + object_name

        # A key contains metadata only.  ReadObj() materializes the object so
        # its ROOT inheritance can be tested below.
        root_object = key.ReadObj()

        if root_object.InheritsFrom("TTree"):
            # Store both pieces: the path is useful to the user, while the
            # object is required later to read branches and leaves.
            discovered_trees.append((object_path, root_object))
        elif root_object.InheritsFrom("TDirectory"):
            # ROOT directories may themselves contain TTrees or more
            # directories, so continue until the full hierarchy is searched.
            discovered_trees.extend(find_trees(root_object, object_path))

    return discovered_trees


def choose_tree(input_file, requested_tree_name: Optional[str]):
    """Select a TTree and return its path, object, and selection explanation.

    The explanation is returned with the ROOT object rather than reconstructed
    later, so the final console summary accurately describes the actual branch
    taken: explicit selection or automatic sole-tree selection.
    """

    # Discover first even for an explicit request.  The list supports useful
    # error messages and resolves a unique bare TTree name if direct lookup
    # with input_file.Get() did not find a path.
    discovered_trees = find_trees(input_file)

    if not discovered_trees:
        raise RuntimeError("No TTrees were found in the input ROOT file.")

    if requested_tree_name:
        # First try ROOT's direct path lookup.  This supports a path such as
        # EventNtuple/ntuple when the tree lives inside a ROOT directory.
        requested_object = input_file.Get(requested_tree_name)
        if requested_object and requested_object.InheritsFrom("TTree"):
            return (
                requested_tree_name,
                requested_object,
                "TTree selection: selected explicitly with --tree.",
            )

        # A bare TTree name is convenient, but it must be unique.  Reusing a
        # name in separate ROOT directories would otherwise be ambiguous.
        name_matches = [
            (tree_path, tree)
            for tree_path, tree in discovered_trees
            if tree.GetName() == requested_tree_name
        ]

        if len(name_matches) == 1:
            selected_path, selected_tree = name_matches[0]
            return (
                selected_path,
                selected_tree,
                "TTree selection: selected explicitly with --tree.",
            )

        # An ambiguous or unknown name must not silently select a different
        # TTree.  Show every valid path so the user can retry unambiguously.
        available_paths = "\n  ".join(tree_path for tree_path, _ in discovered_trees)
        raise RuntimeError(
            "Could not uniquely select TTree '" + requested_tree_name + "'.\n"
            "Available TTree paths:\n  " + available_paths
        )

    if len(discovered_trees) == 1:
        selected_path, selected_tree = discovered_trees[0]
        return (
            selected_path,
            selected_tree,
            "TTree selection: this is the sole TTree in the input file; "
            "it was selected automatically.",
        )

    # More than one TTree exists but no --tree choice was supplied.  Stop here
    # rather than guessing which analysis level the user intended to inspect.
    available_paths = "\n  ".join(tree_path for tree_path, _ in discovered_trees)
    raise RuntimeError(
        "The input file contains more than one TTree.  Select one with --tree.\n"
        "Available TTree paths:\n  " + available_paths
    )


# =============================================================================
# Branch and Leaf Report Helpers
# =============================================================================

def append_leaf_lines(report_lines: List[str], branch, indent: str) -> int:
    """Append leaf details for one branch and return the number of leaves.

    The entry count displayed for each leaf is the owning branch's entry
    count.  This is deliberate: TLeaf describes data within an entry, while
    TBranch is the ROOT object that records the all-entry count.
    """

    # A TBranch owns zero or more TLeaf descriptors.  Start at zero so the
    # returned count remains correct for object branches with no direct leaves.
    leaf_count = 0
    leaf_list = branch.GetListOfLeaves()

    # ROOT can return an empty/null leaf list.  No report text is needed in
    # that case because any nested branch structure is printed separately.
    if not leaf_list:
        return leaf_count

    for leaf in leaf_list:
        # Count every leaf once as it is written, giving the report total a
        # direct one-to-one relationship with the printed leaf lines.
        leaf_count += 1

        # Retrieve the branch that owns this leaf.  Normally it is `branch`,
        # but GetBranch() is the authoritative ROOT association for split
        # objects and makes the displayed source of the entry count explicit.
        leaf_count_branch = leaf.GetBranch()
        leaf_entries = leaf_count_branch.GetEntries() if leaf_count_branch else branch.GetEntries()

        # Type and static length describe how ROOT stores one value.  For a
        # variable-length leaf, the leaf-count object below identifies which
        # companion leaf provides the event-by-event length.
        leaf_type = leaf.GetTypeName()
        static_length = leaf.GetLenStatic()

        leaf_count_object = leaf.GetLeafCount()
        variable_length_note = ""
        if leaf_count_object:
            variable_length_note = ", variable length controlled by " + leaf_count_object.GetName()

        # Append lines to an in-memory list instead of writing repeatedly to
        # disk.  This lets build_tree_report() add headings and totals in a
        # controlled order before write_report() performs the single write.
        report_lines.append(
            indent
            + "Leaf: "
            + leaf.GetName()
            + " | Type: "
            + leaf_type
            + " | Entries (owning branch): "
            + str(leaf_entries)
            + " | Static length: "
            + str(static_length)
            + variable_length_note
        )

    return leaf_count


def append_branch_lines(
    report_lines: List[str], branch, branch_index: List[int], indent: str = ""
) -> Tuple[int, int]:
    """Append one branch hierarchy and return its branch and leaf totals.

    A split C++ object can create a parent branch with nested sub-branches.
    This recursive routine preserves that hierarchy through indentation while
    assigning one report-wide, sequential branch number to every branch.
    """

    # branch_index is a one-element list so recursive calls share and update
    # the same counter.  Integers themselves are immutable in Python.
    branch_index[0] += 1
    this_branch_number = branch_index[0]
    branch_entries = branch.GetEntries()
    branch_class_name = branch.GetClassName()
    branch_title = branch.GetTitle()

    # The branch line is intentionally concise: name identifies the data,
    # entries show how many events ROOT recorded, and class identifies object
    # branches.  Primitive/split branches have no class-name string.
    report_lines.append(
        indent
        + "Branch "
        + str(this_branch_number)
        + ": "
        + branch.GetName()
        + " | Entries: "
        + str(branch_entries)
        + " | Class: "
        + (branch_class_name if branch_class_name else "(primitive/split branch)")
    )

    if branch_title:
        # ROOT titles often contain the leaf-list description.  Preserve it
        # because it can be more informative than a simple class name.
        report_lines.append(indent + "  Title: " + branch_title)

    # Count this branch itself before recursively accumulating its descendants.
    total_branches = 1
    total_leaves = append_leaf_lines(report_lines, branch, indent + "  ")

    # A normal primitive branch has no sub-branches.  Object/split branches
    # may have them, and their output is indented beneath the parent branch.
    sub_branch_list = branch.GetListOfBranches()
    if sub_branch_list and sub_branch_list.GetEntries() > 0:
        report_lines.append(indent + "  Sub-branches:")
        for sub_branch in sub_branch_list:
            # Recursion performs the same printing/counting for every depth
            # of a split-object hierarchy.
            sub_branch_total, sub_leaf_total = append_branch_lines(
                report_lines, sub_branch, branch_index, indent + "    "
            )
            total_branches += sub_branch_total
            total_leaves += sub_leaf_total

    return total_branches, total_leaves


def build_tree_report(tree_path: str, tree) -> Tuple[List[str], int, int]:
    """Build all lines for the saved report and return branch/leaf totals.

    This function is deliberately separate from file I/O: it creates a full,
    reviewable representation first, then write_report() writes it only after
    all metadata, branches, leaves, and totals have been collected.
    """

    # Begin with file-level metadata before listing the detailed hierarchy.
    # These lines let the saved report stand alone outside the ROOT session.
    report_lines = [
        DIVIDER,
        "ROOT TTree Structure Report",
        DIVIDER,
        "Selected TTree path: " + tree_path,
        "TTree name: " + tree.GetName(),
        "TTree title: " + tree.GetTitle(),
        "TTree entries: " + str(tree.GetEntries()),
        SUBDIVIDER,
        "Branch and Leaf Structure",
        SUBDIVIDER,
    ]

    # GetListOfBranches() contains only branches directly owned by the TTree.
    # append_branch_lines() is responsible for visiting deeper sub-branches.
    top_level_branches = tree.GetListOfBranches()
    if not top_level_branches or top_level_branches.GetEntries() == 0:
        report_lines.append("No branches were found in this TTree.")
        return report_lines, 0, 0

    # The mutable branch index is shared across top-level iterations and all
    # recursive descendants, which makes numbering continuous in the report.
    branch_index = [0]
    total_branches = 0
    total_leaves = 0

    for branch in top_level_branches:
        # Add each independent top-level hierarchy and combine its counts into
        # the whole-tree totals reported at the end of the text file.
        branch_total, leaf_total = append_branch_lines(report_lines, branch, branch_index)
        total_branches += branch_total
        total_leaves += leaf_total

    # End with totals after the full hierarchy so a reader can verify the
    # extent of the printed structure without manually counting lines.
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
    """Write the complete report, creating the requested output directory.

    The user may provide an alternate --output path.  The same directory
    creation logic is retained for that path, provided the user has permission
    to create folders there.
    """

    # abspath permits a bare filename, a relative path, or an absolute path;
    # dirname then identifies precisely which folder must exist.
    output_directory = os.path.dirname(os.path.abspath(output_text_file))
    if output_directory and not os.path.isdir(output_directory):
        # This output folder is part of the requested program behavior.  Its
        # automatic creation means a first use does not fail merely because
        # TxtOutputs/TTreeDumps has not been made by hand yet.
        os.makedirs(output_directory, exist_ok=True)

    # Use write mode deliberately: the report represents one fresh inspection
    # of the selected TTree, so a rerun should replace an older report with the
    # same source-derived name instead of mixing two runs together.
    with open(output_text_file, "w", encoding="utf-8") as output_stream:
        # Joining once makes each report item one text line and guarantees a
        # conventional trailing newline for terminal and editor compatibility.
        output_stream.write("\n".join(report_lines) + "\n")


# =============================================================================
# Main Program
# =============================================================================

def main() -> int:
    """Open the file, build the report, write it, and print the final summary."""

    # Construct the command interface, then convert the user's typed options
    # into the arguments object used by every later program stage.
    parser = build_argument_parser()
    arguments = parser.parse_args()

    # -------------------------------------------------------------------------
    # 1. Validate the input path before ROOT attempts to open it.
    # -------------------------------------------------------------------------
    if not os.path.isfile(arguments.input_root_file):
        print("ERROR: input ROOT file does not exist: " + arguments.input_root_file)
        return 1

    # ROOT is only being used to inspect file metadata; batch mode prevents it
    # from creating graphical canvases during command-line use.
    ROOT.gROOT.SetBatch(True)

    # -------------------------------------------------------------------------
    # 2. Open the input ROOT file.
    # -------------------------------------------------------------------------
    input_file = ROOT.TFile.Open(arguments.input_root_file, "READ")
    if not input_file or input_file.IsZombie():
        print("ERROR: could not open ROOT file: " + arguments.input_root_file)
        return 1

    try:
        # ---------------------------------------------------------------------
        # 3. Select the requested TTree and build the complete text report.
        # ---------------------------------------------------------------------
        tree_path, selected_tree, selection_message = choose_tree(
            input_file, arguments.tree_name
        )
        report_lines, branch_total, leaf_total = build_tree_report(tree_path, selected_tree)

        # ---------------------------------------------------------------------
        # 4. Save the report to a plain-text file.
        # ---------------------------------------------------------------------
        output_text_file = arguments.output_text_file
        if not output_text_file:
            output_text_file = default_output_name(arguments.input_root_file)

        write_report(output_text_file, report_lines)

        # ---------------------------------------------------------------------
        # 5. Print the requested concise console summary.
        # ---------------------------------------------------------------------
        print(DIVIDER)
        print("ROOT TTree Dump Complete")
        print(selection_message)
        print("Tree name: " + selected_tree.GetName())
        print("Branch number: " + str(branch_total))
        print("Leaf number: " + str(leaf_total))
        print("Level of analysis structure: " + arguments.analysis_level)
        print("Saved text report: " + os.path.abspath(output_text_file))
        print(DIVIDER)

    except RuntimeError as runtime_error:
        # Expected selection/output failures are presented as concise messages
        # instead of an internal Python traceback, then reported as failure.
        print("ERROR: " + str(runtime_error))
        return 1
    finally:
        # This cleanup always runs after a successfully opened ROOT file,
        # including after a selection or report-writing error.  Explicitly
        # closing it avoids leaving handles open in a persistent session.
        input_file.Close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

