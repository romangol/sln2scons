A python script to convert Microsoft Visual Studio 2005 solution files (`*.sln`) and the associated project files (`*.vcproj`) into a set of SCons files (SConstruct and SConscript).

The class Sln2SCons does all the work, parses the sln and vcproj files and generates a main SConstruct and one SConscript for every project in the solution.