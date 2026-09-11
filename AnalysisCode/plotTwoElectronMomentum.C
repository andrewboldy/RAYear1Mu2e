// plotTwoElectronMomentum.C
//
// Read a CSV of two-electron momentum vectors and make the requested ROOT
// plots.  The CSV must have the columns:
// event,momNumber,px,py,pz,p,theta,phi,magnitude4,energy
//
// Run from ROOT:
//   root -l -q 'CreatedCode/plotTwoElectronMomentum.C+("momenta.csv")'
//
// The second argument names a multipage PDF containing all plots.

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include <TCanvas.h>
#include <TGraph2D.h>
#include <TH1D.h>
#include <TH2D.h>
#include <TMath.h>
#include <TPad.h>
#include <TStyle.h>
#include <TSystem.h>

namespace two_electron_momentum_detail {

struct Momentum {
  double px = 0.0;
  double py = 0.0;
  double pz = 0.0;
  double p = 0.0;
  double theta = 0.0;
  double phi = 0.0;
};

typedef std::map<int, std::map<int, Momentum> > EventMap;

bool parseLine(const std::string& line, int& event, int& momNumber,
               Momentum& momentum) {
  std::stringstream stream(line);
  std::string field;
  std::vector<std::string> fields;
  while (std::getline(stream, field, ',')) fields.push_back(field);
  if (fields.size() < 8) return false;

  try {
    event = std::stoi(fields[0]);
    momNumber = std::stoi(fields[1]);
    momentum.px = std::stod(fields[2]);
    momentum.py = std::stod(fields[3]);
    momentum.pz = std::stod(fields[4]);
    momentum.p = std::stod(fields[5]);
    momentum.theta = std::stod(fields[6]);
    momentum.phi = std::stod(fields[7]);
  } catch (const std::exception&) {
    return false;
  }
  return momNumber > 0;
}

double momentumMagnitude(const Momentum& momentum) {
  return std::sqrt(momentum.px * momentum.px + momentum.py * momentum.py +
                   momentum.pz * momentum.pz);
}

double openingAngle(const Momentum& first, const Momentum& second) {
  const double firstMagnitude = momentumMagnitude(first);
  const double secondMagnitude = momentumMagnitude(second);
  if (firstMagnitude == 0.0 || secondMagnitude == 0.0) return -1.0;
  const double dot = first.px * second.px + first.py * second.py +
                     first.pz * second.pz;
  const double cosine = std::max(-1.0, std::min(1.0,
    dot / (firstMagnitude * secondMagnitude)));
  return std::acos(cosine);
}

void setupPad() {
  gPad->SetTicks(1, 1);
  gPad->SetGrid(1, 1);
  gPad->SetLeftMargin(0.13);
  gPad->SetRightMargin(0.14);
  gPad->SetBottomMargin(0.12);
}

void style2D(TH2D& histogram) {
  histogram.SetStats(false);
  histogram.GetXaxis()->SetTitleSize(0.050);
  histogram.GetYaxis()->SetTitleSize(0.050);
  histogram.GetXaxis()->SetLabelSize(0.040);
  histogram.GetYaxis()->SetLabelSize(0.040);
}

} // namespace two_electron_momentum_detail

void plotTwoElectronMomentum(
  const char* csvFile,
  const char* outputPdf = "twoElectronMomentumPlots.pdf") {
  using namespace two_electron_momentum_detail;

  std::ifstream input(csvFile);
  if (!input) {
    std::cerr << "ERROR: cannot open CSV file: " << csvFile << std::endl;
    return;
  }

  std::string header;
  std::getline(input, header);
  if (header.find("event") == std::string::npos ||
      header.find("px") == std::string::npos) {
    std::cerr << "ERROR: CSV header does not look like the expected momentum CSV."
              << std::endl;
    return;
  }

  EventMap events;
  std::string line;
  int lineNumber = 1;
  int tracksRead = 0;
  while (std::getline(input, line)) {
    ++lineNumber;
    if (line.empty()) continue;
    int event = 0, momNumber = 0;
    Momentum momentum;
    if (!parseLine(line, event, momNumber, momentum)) {
      std::cerr << "WARNING: skipping malformed line " << lineNumber << std::endl;
      continue;
    }
    if (events[event].count(momNumber)) {
      std::cerr << "WARNING: duplicate event " << event << ", momNumber "
                << momNumber << "; keeping the first row." << std::endl;
      continue;
    }
    events[event][momNumber] = momentum;
    ++tracksRead;
  }

  TH1D momentumMagnitudeHist("momentumMagnitude", "Momentum magnitude;|p| [MeV/c];Tracks", 80, 0.0, 80.0);
  TH1D openingAngleHist("openingAngle", "Opening angle between momentum 1 and 2;Opening angle [rad];Events", 72, 0.0, TMath::Pi());
  TH2D cosThetaVsPhi("cosThetaVsPhi", "cos(#theta) vs #phi;#phi [rad];cos(#theta)", 72, -TMath::Pi(), TMath::Pi(), 60, -1.0, 1.0);
  TH2D theta1VsTheta2("theta1VsTheta2", "#theta_{1} vs #theta_{2};#theta_{1} [rad];#theta_{2} [rad]", 60, 0.0, TMath::Pi(), 60, 0.0, TMath::Pi());
  TH2D thetaVsPhiForward("thetaVsPhiForward", "#theta vs #phi (forward, p_{z} > 0);#phi [rad];#theta [rad]", 72, -TMath::Pi(), TMath::Pi(), 60, 0.0, TMath::Pi());
  TH2D thetaVsPhiBackward("thetaVsPhiBackward", "#theta vs #phi (backward, p_{z} < 0);#phi [rad];#theta [rad]", 72, -TMath::Pi(), TMath::Pi(), 60, 0.0, TMath::Pi());
  style2D(cosThetaVsPhi);
  style2D(theta1VsTheta2);
  style2D(thetaVsPhiForward);
  style2D(thetaVsPhiBackward);

  TGraph2D momentum3D;
  momentum3D.SetTitle("Three-dimensional momentum vectors;p_{x} [MeV/c];p_{y} [MeV/c];p_{z} [MeV/c]");
  momentum3D.SetMarkerStyle(20);
  momentum3D.SetMarkerSize(0.9);
  momentum3D.SetMarkerColor(kAzure + 2);

  int graphPoint = 0;
  int pairedEvents = 0;
  for (EventMap::const_iterator event = events.begin(); event != events.end(); ++event) {
    const std::map<int, Momentum>& momenta = event->second;
    for (std::map<int, Momentum>::const_iterator track = momenta.begin();
         track != momenta.end(); ++track) {
      const Momentum& momentum = track->second;
      const double calculatedP = momentumMagnitude(momentum);
      momentumMagnitudeHist.Fill(calculatedP);
      cosThetaVsPhi.Fill(momentum.phi, std::cos(momentum.theta));
      if (momentum.pz > 0.0) thetaVsPhiForward.Fill(momentum.phi, momentum.theta);
      if (momentum.pz < 0.0) thetaVsPhiBackward.Fill(momentum.phi, momentum.theta);
      momentum3D.SetPoint(graphPoint++, momentum.px, momentum.py, momentum.pz);
    }

    std::map<int, Momentum>::const_iterator first = momenta.find(1);
    std::map<int, Momentum>::const_iterator second = momenta.find(2);
    if (first != momenta.end() && second != momenta.end()) {
      const double angle = openingAngle(first->second, second->second);
      if (angle >= 0.0) openingAngleHist.Fill(angle);
      theta1VsTheta2.Fill(first->second.theta, second->second.theta);
      ++pairedEvents;
    } else {
      std::cerr << "WARNING: event " << event->first
                << " does not have both momNumber 1 and 2; excluded from pair plots."
                << std::endl;
    }
  }

  gStyle->SetOptStat(0);
  TCanvas canvas("momentumPlots", "Two-electron momentum plots", 1600, 1000);
  canvas.Divide(3, 2);
  canvas.cd(1); setupPad(); momentumMagnitudeHist.Draw("HIST");
  canvas.cd(2); setupPad(); openingAngleHist.Draw("HIST");
  canvas.cd(3); setupPad(); cosThetaVsPhi.Draw("COLZ");
  canvas.cd(4); setupPad(); theta1VsTheta2.Draw("COLZ");
  canvas.cd(5); setupPad(); thetaVsPhiForward.Draw("COLZ");
  canvas.cd(6); setupPad(); thetaVsPhiBackward.Draw("COLZ");
  canvas.Print((std::string(outputPdf) + "[").c_str());
  canvas.Print(outputPdf);

  TCanvas momentumCanvas("momentum3D", "Three-dimensional momentum", 900, 800);
  momentumCanvas.SetTicks(1, 1);
  momentumCanvas.SetGrid(1, 1);
  momentumCanvas.SetTheta(28.0);
  momentumCanvas.SetPhi(35.0);
  momentum3D.Draw("P0");
  momentumCanvas.Print(outputPdf);
  momentumCanvas.Print((std::string(outputPdf) + "]").c_str());

  std::cout << "Read " << tracksRead << " momentum rows from " << events.size()
            << " events (" << pairedEvents << " complete two-momentum events)."
            << std::endl;
  std::cout << "Wrote plots to " << outputPdf << std::endl;
}

