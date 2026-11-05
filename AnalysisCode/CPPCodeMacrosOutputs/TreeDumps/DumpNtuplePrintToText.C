/*
  DumpNtuplePrintToText.C

  Purpose
  -------
  This ROOT macro opens a ROOT file, moves into a directory inside that file,
  retrieves a TTree, and writes the output of TTree::Print() to a plain text
  file.  It is intended for quickly documenting or inspecting the branch
  structure of a TTree such as:

      root -l [filename]
      EventNtuple->cd();
      ntuple->Print();

  The important difference is that this macro sends the Print() output to a
  .txt file instead of only displaying it in the terminal.

  Typical Usage
  -------------
  From a terminal, run:

      root -l -b -q 'DumpNtuplePrintToText.C("input.root")'

  This will create:

      ntuple_printout.txt

  in the directory from which you ran ROOT.

  You may also choose a custom output text file:

      root -l -b -q 'DumpNtuplePrintToText.C("input.root", "my_tree_structure.txt")'

  If your directory or tree has a different name, pass those too:

      root -l -b -q 'DumpNtuplePrintToText.C("input.root", "tree.txt", "MyDirectory", "MyTree")'

  Notes
  -----
  The default directory name is "EventNtuple".
  The default tree name is "ntuple".

  The macro uses gSystem->RedirectOutput(...) because TTree::Print() writes
  through ROOT's normal output stream.  RedirectOutput captures that terminal
  output and places it in the requested text file.
*/

#include <iostream>

#include "TDirectory.h"
#include "TFile.h"
#include "TSystem.h"
#include "TTree.h"

void DumpNtuplePrintToText(const char* inputRootFile,
                           const char* outputTextFile = "ntuple_printout.txt",
                           const char* directoryName = "EventNtuple",
                           const char* treeName = "ntuple")
{
    // ---------------------------------------------------------------------
    // 1. Check that the user supplied an input ROOT file name.
    // ---------------------------------------------------------------------
    // ROOT will allow a null C-string to be passed in accidentally from some
    // macro calls, so this gives a clear message before trying to open it.
    if (!inputRootFile || inputRootFile[0] == '\0') {
        std::cerr << "Error: no input ROOT file was provided." << std::endl;
        std::cerr << "Example usage:" << std::endl;
        std::cerr << "  root -l -b -q 'DumpNtuplePrintToText.C(\"input.root\")'" << std::endl;
        return;
    }

    // ---------------------------------------------------------------------
    // 2. Open the ROOT file.
    // ---------------------------------------------------------------------
    // TFile::Open returns a pointer to the opened file.  If the file cannot
    // be opened, ROOT may return a null pointer or a "zombie" file object.
    TFile* inputFile = TFile::Open(inputRootFile, "READ");

    if (!inputFile || inputFile->IsZombie()) {
        std::cerr << "Error: could not open ROOT file: " << inputRootFile << std::endl;
        return;
    }

    // ---------------------------------------------------------------------
    // 3. Find the directory that contains the TTree.
    // ---------------------------------------------------------------------
    // This corresponds to the interactive ROOT command:
    //
    //     EventNtuple->cd();
    //
    // Instead of assuming EventNtuple already exists as an interactive
    // variable, this retrieves it by name from the file.
    TDirectory* eventDirectory = inputFile->GetDirectory(directoryName);

    if (!eventDirectory) {
        std::cerr << "Error: could not find directory named "
                  << directoryName << " in file " << inputRootFile << std::endl;
        inputFile->Close();
        return;
    }

    // Move ROOT's current directory context into the selected directory.
    // This mirrors the interactive EventNtuple->cd() command and also keeps
    // any relative object lookup behavior familiar.
    eventDirectory->cd();

    // ---------------------------------------------------------------------
    // 4. Find the TTree inside that directory.
    // ---------------------------------------------------------------------
    // This corresponds to the interactive ROOT object named "ntuple".
    TTree* ntupleTree = dynamic_cast<TTree*>(eventDirectory->Get(treeName));

    if (!ntupleTree) {
        std::cerr << "Error: could not find TTree named "
                  << treeName << " inside directory " << directoryName << std::endl;
        inputFile->Close();
        return;
    }

    // ---------------------------------------------------------------------
    // 5. Redirect ROOT output to the chosen text file.
    // ---------------------------------------------------------------------
    // TTree::Print() writes to ROOT's output stream, which normally appears
    // in the terminal.  RedirectOutput sends that stream to outputTextFile.
    //
    // The second argument, "w", means write mode.  If outputTextFile already
    // exists, it will be overwritten.
    gSystem->RedirectOutput(outputTextFile, "w");

    // ---------------------------------------------------------------------
    // 6. Print the tree structure.
    // ---------------------------------------------------------------------
    // This is the same core operation as:
    //
    //     ntuple->Print();
    //
    // but because output is currently redirected, the printed TTree structure
    // is saved to the text file.
    ntupleTree->Print();

    // ---------------------------------------------------------------------
    // 7. Restore normal terminal output.
    // ---------------------------------------------------------------------
    // Calling RedirectOutput(0) turns off the redirection so later messages
    // from ROOT or from this macro return to the terminal.
    gSystem->RedirectOutput(0);

    // Let the user know where the output went.  This message appears in the
    // terminal, not in the output text file, because redirection is now off.
    std::cout << "Wrote TTree::Print() output for "
              << directoryName << "/" << treeName
              << " to " << outputTextFile << std::endl;

    // ---------------------------------------------------------------------
    // 8. Close the input file.
    // ---------------------------------------------------------------------
    // Closing the file is good housekeeping and avoids leaving file handles
    // open during repeated ROOT sessions.
    inputFile->Close();
}

