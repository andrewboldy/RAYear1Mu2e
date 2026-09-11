#include <iostream>
#include <fstream>
#include <string>
#include <regex>
#include <cmath>
#include <iomanip>

struct MomentumEvent {
    int momNumber;

    double px;
    double py;
    double pz;

    double p;
    double theta;
    double phi;

    double magnitude4;
    double energy;
};

void parseB2BOutput(const char* inputFile)
{
    // ------------------------------------------------------------
    // Output file
    // ------------------------------------------------------------

    const std::string outputFile = "B2BGenOutputTextFileParsed.txt";

    std::ifstream infile(inputFile);
    std::ofstream outfile(outputFile);

    if (!infile.is_open()) {
        std::cerr << "Error: Could not open input file: "
                  << inputFile << std::endl;
        return;
    }

    if (!outfile.is_open()) {
        std::cerr << "Error: Could not create output file: "
                  << outputFile << std::endl;
        return;
    }

    // ------------------------------------------------------------
    // Output header
    // ------------------------------------------------------------

    outfile << "event,momNumber,px,py,pz,p,theta,phi,magnitude4,energy\n";

    // ------------------------------------------------------------
    // Regular expression for momentum lines
    // ------------------------------------------------------------

    const std::regex momentumRegex(
        R"(MomNumber:\s*(\d+)\s*\|\|\s*)"
        R"(Cartesian vector:\s*\(\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*\)\s*\|\|\s*)"
        R"(Spherical Vector:\s*\(\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*,\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*\)\s*\|\|\s*)"
        R"(Magnitude of 4 Vector:\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*\|\|\s*)"
        R"(Energy:\s*)"
        R"(([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?))"
    );

    std::string line;
    std::smatch match;

    // ------------------------------------------------------------
    // Event bookkeeping
    // ------------------------------------------------------------

    int eventCount = 0;
    int backToBackCount = 0;

    // Store the two electrons belonging to the current event
    MomentumEvent electron1;
    MomentumEvent electron2;

    bool haveElectron1 = false;

    // Tolerance for determining whether cos(theta) is -1
    const double tolerance = 1.0e-6;

    // ------------------------------------------------------------
    // Read file line by line
    // ------------------------------------------------------------

    while (std::getline(infile, line)) {

        // Ignore everything that is not a MomNumber line
        if (line.find("MomNumber:") == std::string::npos) {
            continue;
        }

        // Attempt to parse line
        if (!std::regex_search(line, match, momentumRegex)) {
            std::cerr << "Warning: Could not parse line:\n"
                      << line << "\n";
            continue;
        }

        // --------------------------------------------------------
        // Extract momentum information
        // --------------------------------------------------------

        MomentumEvent current;

        current.momNumber = std::stoi(match[1].str());

        current.px = std::stod(match[2].str());
        current.py = std::stod(match[3].str());
        current.pz = std::stod(match[4].str());

        current.p = std::stod(match[5].str());
        current.theta = std::stod(match[6].str());
        current.phi = std::stod(match[7].str());

        current.magnitude4 = std::stod(match[8].str());
        current.energy = std::stod(match[9].str());

        // --------------------------------------------------------
        // First electron in event
        // --------------------------------------------------------

        if (current.momNumber == 1) {

            electron1 = current;
            haveElectron1 = true;
        }

        // --------------------------------------------------------
        // Second electron in event
        // --------------------------------------------------------

        else if (current.momNumber == 2) {

            if (!haveElectron1) {
                std::cerr << "Warning: Found MomNumber 2 without "
                          << "a preceding MomNumber 1.\n";
                continue;
            }

            electron2 = current;

            // One complete physical event has now been found
            ++eventCount;

            // ----------------------------------------------------
            // Write both electrons with the SAME event number
            // ----------------------------------------------------

            outfile << eventCount << ","
                    << electron1.momNumber << ","
                    << electron1.px << ","
                    << electron1.py << ","
                    << electron1.pz << ","
                    << electron1.p << ","
                    << electron1.theta << ","
                    << electron1.phi << ","
                    << electron1.magnitude4 << ","
                    << electron1.energy << "\n";

            outfile << eventCount << ","
                    << electron2.momNumber << ","
                    << electron2.px << ","
                    << electron2.py << ","
                    << electron2.pz << ","
                    << electron2.p << ","
                    << electron2.theta << ","
                    << electron2.phi << ","
                    << electron2.magnitude4 << ","
                    << electron2.energy << "\n";

            // ----------------------------------------------------
            // Check whether the two electrons are back-to-back
            // ----------------------------------------------------

            const double dot =
                electron1.px * electron2.px +
                electron1.py * electron2.py +
                electron1.pz * electron2.pz;

            const double magnitude1 =
                std::sqrt(
                    electron1.px * electron1.px +
                    electron1.py * electron1.py +
                    electron1.pz * electron1.pz
                );

            const double magnitude2 =
                std::sqrt(
                    electron2.px * electron2.px +
                    electron2.py * electron2.py +
                    electron2.pz * electron2.pz
                );

            if (magnitude1 > 0.0 && magnitude2 > 0.0) {

                const double cosAngle =
                    dot / (magnitude1 * magnitude2);

                // Perfectly back-to-back:
                // cos(theta) = -1
                if (std::abs(cosAngle + 1.0) < tolerance) {
                    ++backToBackCount;
                }
            }

            // Reset for the next event
            haveElectron1 = false;
        }
    }

    // ------------------------------------------------------------
    // Check for incomplete final event
    // ------------------------------------------------------------

    if (haveElectron1) {
        std::cerr << "Warning: Input file ended with a MomNumber 1 "
                  << "without a corresponding MomNumber 2.\n";
    }

    // ------------------------------------------------------------
    // Calculate percentage
    // ------------------------------------------------------------

    double backToBackPercentage = 0.0;

    if (eventCount > 0) {
        backToBackPercentage =
            100.0 *
            static_cast<double>(backToBackCount) /
            static_cast<double>(eventCount);
    }

    // ------------------------------------------------------------
    // Print summary
    // ------------------------------------------------------------

    std::cout << "\n";
    std::cout << "========================================\n";
    std::cout << "B2B Generator Parsing Summary\n";
    std::cout << "========================================\n";

    std::cout << "Input file: "
              << inputFile << "\n";

    std::cout << "Total events processed: "
              << eventCount << "\n";

    std::cout << "Back-to-back events: "
              << backToBackCount << "\n";

    std::cout << std::fixed << std::setprecision(4);

    std::cout << "Back-to-back percentage: "
              << backToBackPercentage << "%\n";

    std::cout << "========================================\n";

    infile.close();
    outfile.close();

    std::cout << "\nParsed output written to: "
              << outputFile << std::endl;
}
