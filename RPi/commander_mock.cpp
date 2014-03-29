#include <iostream>
#include <string>
#include <fstream>

int main() {
    std::string s;
    std::ofstream myfile;
    myfile.open("/tmp/log.txt", std::ios::out);
    while(std::cin.good()) {
        std::getline(std::cin, s);
        std::cout << s << std::endl;
        myfile << s << std::endl;
    }
    myfile.close();

    return 0;
}
