#
# sln2scons.py
#
# A python script to convert Visual Studio 2005 solution and projects to SCons's scripts
#
# Copyright (c) 2008, AlferSoft (www.alfersoft.com.ar)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the company nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY AlferSoft ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL AlferSoft BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import array
import re
import os
import string
from os import path
from xml.dom.minidom import parseString
from pathcorrect import CaseCorrect

class Project:
    def __init__(self):
        self.id = ""
        self.name = ""
        self.path = ""
        self.abspath = ""
        self.intdir = ""
        self.outdir = ""
        self.outfile = ""
        self.implib = ""
        self.implibdir = ""
        self.conftype = ""
        self.addlib = []
        self.incdir = []
        self.dependencies = []
        self.sorted = False

class Folder:
    def __init__(self):
        self.id = ""
        self.name = ""

class Sln2SCons:
    """Parse Microsoft Visual C solution file and convert to SCons.
    
    Keyword arguments:
    slnFile -- solution file name
    outputPath -- place where base SConstruct will be created (default current),
                  output and library paths will be relative to this one
    """
    def __init__(self, slnFile, exlist=[], dirrepl=[], librepl=[], outputPath=''):
        casedir = CaseCorrect()
        file = open(casedir.correct(slnFile),"r")
        arrproj=[]
        arrfolder=[]
        # example of pattern #1
        # Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AASSODDLL", "DevSrc\Drivers30\MW\AASSODDLL\AASSODDLL.vcproj", "{A709D276-7285-40A7-9D4D-9D9B2949EEDA}"
        pat1 = re.compile(r"""
         Project                                 # skip Project
         \(\"\{(?P<type>[0-9a-fA-F\-]*)\}\"\)    # extract type
         \s*=\s*                                 # skip =
         \"(?P<name>[\w_\-]*)\"                  # extract name
         \s*,\s*                                 # skip ,
         \"(?P<path>[\w:\\/\._\-]*)\"            # extract path
         \s*,\s*                                 # skip ,
         \"\{(?P<id>[0-9a-fA-F\-]*)\}\"          # extract id
         (.*)$                                   # skip the rest
         """, re.VERBOSE)
        # example of pattern #2
        # ProjectSection(ProjectDependencies) = postProject
        pat2 = re.compile(r"""
         \s*                                     # skip initial spaces
         ProjectSection
         \(ProjectDependencies\)
         (.*)$
         """, re.VERBOSE)
        # example of pattern #3
        # {B746B5A2-F8F1-4A30-9C72-69348B3DCBEC} = {B746B5A2-F8F1-4A30-9C72-69348B3DCBEC}
        pat3 = re.compile(r"""
         \s*                                     # skip initial spaces
         \{(?P<id1>[0-9a-fA-F\-]*)\}             # extract id1
         \s*=\s*                                 # skip =
         \{(?P<id2>[0-9a-fA-F\-]*)\}             # extract id2
         (.*)$                                   # skip the rest
         """, re.VERBOSE)
        # example of pattern #4
        # EndProjectSection
        pat4 = re.compile(r"""
         \s*                                     # skip initial spaces
         EndProjectSection
         (.*)$
         """, re.VERBOSE)
        # example of pattern #5
        # EndProject
        pat5 = re.compile(r"""
         \s*                                     # skip initial spaces
         EndProject
         (.*)$
         """, re.VERBOSE)
        proj = None
        type_project = "8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942"
        type_folder = "2150E333-8FDC-42A3-9474-1A3956D46DE8"
        self.slnDir = ""
        self.absSlnDir = path.join(path.normpath(path.join(os.getcwd(), self.slnDir) + "/"), "")
        self.outSlnDir = path.join(path.normpath(path.join(os.getcwd() + "/" + outputPath, self.slnDir) + "/"), "")
        print "Absolute solution dir: " + self.absSlnDir
        self.config = "Release"
        for line in file.readlines():
            match = pat1.search(line)
            if match:
                if type_project == match.group("type"):
                    proj = Project()
                    proj.id = match.group("id")
                    proj.name = match.group("name")
                    joined = path.join(os.getcwd(), path.join(path.dirname(slnFile),match.group("path")).replace("\\", "/")).replace("\\", "/")
                    proj.path = self._relativePath(os.getcwd().replace("\\", "/"), joined).replace("\\", "/")
                    proj.abspath = path.normpath(path.join(os.getcwd(), path.dirname(proj.path))) + "/"
                elif type_folder == match.group("type"):
                    folder = Folder()
                    folder.id = match.group("id")
                    folder.name = match.group("name")
                    arrfolder.append(folder)
            else:
                match = pat3.search(line)
                if match and proj:
                    proj.dependencies.append(match.group("id1"))
                else:
                    match = pat5.search(line)
                    if match and proj:
                        arrproj.append(proj)
                        proj = None
        file.close()
        # get output name for each project
        for proj in arrproj:
            # merge path with solution directory
            vcprojContent = self._getFileContent(casedir.correct(proj.path))
            vcprojDoc = parseString(vcprojContent)
            confs = vcprojDoc.documentElement.getElementsByTagName("Configurations")
            if confs:
                list = confs[0].getElementsByTagName("Configuration")
            if len(list) > 0:
                for elem in list:
                    if elem.getAttribute("Name") == self.config + "|Win32":
                        for tool in elem.getElementsByTagName("Tool"):
                            if tool.getAttribute("Name") == "VCLinkerTool":
                                proj.outfile, dummyext = path.splitext(path.basename(self._processMacros(tool.getAttribute("OutputFile"), proj, False)))
                                proj.outfile = proj.outfile.replace("\\", "/")
            if proj.outfile == "":
                proj.outfile = proj.name
        # sort by dependency
        projsorted = []
        for proj in arrproj:
            if len(proj.dependencies) == 0:
                proj.sorted = True
                projsorted.append(proj)
        allsorted = False
        maxdep = 1
        toomuch = 0
        # not very clever sort
        while not allsorted:
            foundone = False
            cntsort = 0
            for proj in arrproj:
                if proj.sorted:
                    cntsort = cntsort + 1
                if not proj.sorted and len(proj.dependencies) == maxdep:
                    foundone = True
                    canadd = 0
                    # find dependant project
                    for dep in proj.dependencies:
                        for projdep in arrproj:
                            if projdep.id == dep and projdep.sorted:
                                canadd = canadd + 1
                    if canadd != maxdep:
                        # try next
                        continue
                    # add it
                    proj.sorted = True
                    projsorted.append(proj)
            if not foundone or toomuch > 1000:
                toomuch = 0
                maxdep = maxdep + 1
            else:
                toomuch = toomuch + 1
            if cntsort == len(arrproj) or maxdep >= 100:
                break
        # add unsorted projects (more than 100 dependencies)
        for proj in arrproj:
            if not proj.sorted:
                proj.sorted = True
                projsorted.append(proj)
        arrproj = projsorted
        # create output file
        for proj in arrproj:
            # merge path with solution directory
            vcprojContent = self._getFileContent(casedir.correct(proj.path))
            if not vcprojContent:
                print "WARNING!!! File: " + proj.path + " (" + casedir.correct(proj.path) + ") not found!!!"
                continue
            vcprojDoc = parseString(vcprojContent)
            confs = vcprojDoc.documentElement.getElementsByTagName("Configurations")
            if confs:
                list = confs[0].getElementsByTagName("Configuration")
            if len(list) > 0:
                for elem in list:
                    if elem.getAttribute("Name") == self.config + "|Win32":
                        proj.conftype = elem.getAttribute("ConfigurationType")
                        proj.intdir = self._relativePath(proj.abspath, self._processMacros(elem.getAttribute("IntermediateDirectory"), proj, True))
                        proj.outdir = self._relativePath(proj.abspath, self._processMacros(elem.getAttribute("OutputDirectory"), proj, True)).lower()
                        for tool in elem.getElementsByTagName("Tool"):
                            if tool.getAttribute("Name") == "VCCLCompilerTool":
                                proj.incdir = self._processMacros(tool.getAttribute("AdditionalIncludeDirectories"), proj, True).replace(",", ";").split(";")
                                proj.incdir = [self._relativePath(proj.abspath, path.join(proj.abspath, elem)) for elem in proj.incdir]
                            if tool.getAttribute("Name") == "VCLinkerTool":
                                proj.addlib = self._processMacros(tool.getAttribute("AdditionalLibraryDirectories"), proj, True).replace(",", ";").split(";")
                                proj.addlib = [self._relativePath(proj.abspath, path.join(proj.abspath, elem)) for elem in proj.addlib]
                                proj.implib = self._processMacros(tool.getAttribute("ImportLibrary"), proj, True)
                                proj.implib = self._relativePath(proj.abspath, path.join(proj.abspath, proj.implib))
                                proj.implibdir = path.dirname(proj.implib) + "/"
                            if tool.getAttribute("Name") == "VCLibrarianTool":
                                if proj.conftype == "4":
                                    proj.outfile, dummyext = path.splitext(path.basename(self._processMacros(tool.getAttribute("OutputFile"), proj, False)))
                    if proj.outfile == "":
                        proj.outfile = proj.name
                    # create SConscript
                    outfile = path.join(casedir.correct(path.dirname(proj.path)), "SConscript").replace("\\", "/")
                    doit = True
                    for elem in exlist:
                        out, repl = elem
                        if out == outfile:
                            doit = False
                            break
                    if not doit:
                        print "Custom script: " + outfile + " (" + repl + ")"
                        continue
                    print "Creating file: " + outfile
                    f = open(outfile, "w+")
                    # header
                    f.write("# sln2scons.py autogenerated SConscript\n")
                    f.write("Import('env')\n")
                    f.write("e = env.Clone()\n")
                    deps = self._recursiveDep(proj, arrproj, dirrepl, librepl)
                    if deps != "":
                        f.write("e['LIBS'] = [" + deps + "]\n")
                    f.write("if not e['MYPLATFORM'] == 'winnt':\n")
                    f.write("    e.Append(LIBS='m')\n")
                    # library directories
                    libpaths = ""
                    for librarydir in proj.addlib:
                        if libpaths != "":
                            libpaths += ", "
                        libpaths += "'" + self._applyDirRepl(dirrepl, librarydir.replace("\\", "/")) + "'"
                    if libpaths != "":
                        f.write("e['LIBPATH'] = [" + libpaths + "]\n")
                    #f.write("env['CPPDEFINES'] = [('i386', '1'), ('LINUX', '1'), ('HAVE_VISIBILITY_HIDDEN_ATTRIBUTE', '1'), ('HAVE_VISIBILITY_PRAGMA', '1'), ('XP_UNIX', '1'), ('_GNU_SOURCE', '1'), ('HAVE_FCNTL_FILE_LOCKING', '1'), ('HAVE_LCHOWN', '1'), ('HAVE_STRERROR', '1'), ('_REENTRANT', '1'), ('HAVE_EXPAT_CONFIG_H', '1')]\n")
                    # include directories
                    incdirs = ""
                    for include in proj.incdir:
                        if incdirs != "":
                            incdirs += ", "
                        incdirs += "'" + self._applyDirRepl(dirrepl, include.replace("\\", "/")) + "/'"
                    if incdirs != "":
                        f.write("e['CPPPATH'] = [" + incdirs + "]\n")
                    f.write("\n")
                    # read source files
                    sources = ""
                    files = vcprojDoc.documentElement.getElementsByTagName("Files")
                    if files:
                        filelist = files[0].getElementsByTagName("File")
                    if len(filelist) > 0:
                        for fi in filelist:
                            filename = fi.getAttribute("RelativePath").replace("\\", "/")
                            filename = path.normpath(filename)
                            for exten in ".c .C .c++ .cc .cpp .cxx".split(" "):
                                if filename.endswith(exten):
                                    if not sources == "":
                                        sources += ", "
                                    sources += "'" + filename + "'"
                                    break
                    # read header files
                    headers = ""
                    if len(filelist) > 0:
                        for fi in filelist:
                            filename = fi.getAttribute("RelativePath").replace("\\", "/")
                            filename = path.normpath(filename)
                            for exten in ".h .hh .h++ .hm .hpp .hxx".split(" "):
                                if filename.endswith(exten):
                                    if not headers == "":
                                        headers += ", "
                                    headers += "'" + filename + "'"
                                    break
                    if proj.conftype == "1":
                        # make executable
                        f.write(proj.name + " = e.Program('" + proj.name + "', [" + sources + "])\n")
                    elif proj.conftype == "2":
                        # make shared library
                        f.write(proj.name + " = e.SharedLibrary('" + proj.name + "', [" + sources + "])\n")
                    elif proj.conftype == "4":
                        # make static library
                        f.write(proj.name + " = e.StaticLibrary('" + proj.name + "', [" + sources + "])\n")
                        #f.write(proj.name + " = e.StaticLibrary('" + proj.name + "', [" + sources + "])\n")
                    f.write("e.Default(" + proj.name + ")\n")
                    f.write("e.Install(Dir('#/' + e['MYPLATFORM'] + '/lib/release'), " + proj.name + ")\n")
                    f.write("\n")
                    f.write("if 'distclean' in COMMAND_LINE_TARGETS:\n")
                    f.write("    Execute(Delete('" + proj.name + "'))\n")
                    f.write("    Execute(Delete(Dir('#/' + e['MYPLATFORM'] + '/bin/release').abspath + '/' + str(" + proj.name + "[0])))\n")
                    f.write("    Execute(Delete(Glob('*.o')))\n")
                    f.write("    Execute(Delete(Glob('*.so')))\n")
                    f.write("    Execute(Delete(Glob('*.os')))\n")
                    f.write("    Execute(Delete(Glob('*.a')))\n")
                    f.write("    Execute(Delete(Glob('*.la')))\n")
                    f.write("    Execute(Delete(Glob('*.dylib')))\n")
                    f.write("\n")
                    f.write("if 'pack' in COMMAND_LINE_TARGETS:\n")
                    f.write("    Execute(Copy(Dir('#/' + e['MYPLATFORM'] + '/bin/release'), " + proj.name + "[0]))\n")
                    f.write("    e.Alias('pack', Dir('#/' + e['MYPLATFORM'] + '/bin/release'))\n")
                    f.write("\n")
                    f.close()
        # create main SConstruct
        outfile = outputPath + "SConstruct"
        f = open(outfile, "w+")
        f.write("# sln2scons.py autogenerated SConstruct\n")
        f.write("import sys\n")
        f.write("\n")
        f.write("if ARGUMENTS.get('debug', 0):\n")
        f.write("    env = Environment(CCFLAGS = '-g')\n")
        f.write("else:\n")
        f.write("    env = Environment()\n")
        f.write("plat = sys.platform\n")
        f.write("if plat.find('linux') != -1:\n")
        f.write("    env['MYPLATFORM']='linux'\n")
        f.write("elif (plat.find('darwin') != -1) or (plat.find('mac') != -1):\n")
        f.write("    env['MYPLATFORM']='macos'\n")
        f.write("elif plat.find('win') != -1:\n")
        f.write("    env['MYPLATFORM']='winnt'\n")
        f.write("else:\n")
        f.write("    env['MYPLATFORM']=plat\n")
        f.write("env['CPPDEFINES'] = [('i386', '1'), ('LINUX', '1'), ('HAVE_VISIBILITY_HIDDEN_ATTRIBUTE', '1'), ('HAVE_VISIBILITY_PRAGMA', '1'), ('XP_UNIX', '1'), ('_GNU_SOURCE', '1'), ('HAVE_FCNTL_FILE_LOCKING', '1'), ('HAVE_LCHOWN', '1'), ('HAVE_STRERROR', '1'), ('_REENTRANT', '1'), ('HAVE_EXPAT_CONFIG_H', '1'), ('USE_APR_UTIL','1')]\n")
        f.write("Execute(Mkdir(Dir('#' + env['MYPLATFORM'] + '/bin/release')))\n")
        f.write("Execute(Mkdir(Dir('#' + env['MYPLATFORM'] + '/lib/release')))\n")
        f.write("Export('env')\n")
        f.write("\n")
        # defines
        #f.write("CPPDEFINES = [('i386', '1'), ('LINUX', '1'), ('HAVE_VISIBILITY_HIDDEN_ATTRIBUTE', '1'), ('HAVE_VISIBILITY_PRAGMA', '1'), ('XP_UNIX', '1'), ('_GNU_SOURCE', '1'), ('HAVE_FCNTL_FILE_LOCKING', '1'), ('HAVE_LCHOWN', '1'), ('HAVE_STRERROR', '1'), ('_REENTRANT', '1'), ('HAVE_EXPAT_CONFIG_H', '1')]")
        # find dependant project
        #for proj in arrproj:
        #    for dep in proj.dependencies:
        #        for projdep in arrproj:
        #            if projdep.id == dep:
        #                f.write("env.Depends('" + proj.name  + "', '" + projdep.name + "')\n")
        #f.write("env.SConscript([")
        for proj in arrproj:
            doit = True
            for elem in exlist:
                out, repl = elem
                if out == path.dirname(proj.path) + "/SConscript":
                    doit = False
                    break
            if doit:
                f.write("env.SConscript('" + self._relativePath(path.normpath(path.join(os.getcwd(), outputPath) + "/"), path.normpath(path.join(os.getcwd(), path.dirname(proj.path)) + "/")) + "/SConscript')\n")
            else:
                if not repl == "":
                    f.write("env.SConscript('" + repl + "')\n")
        f.close()

    def _processMacros(self, str, proj, useabs, useout = False):
        slndir = self.slnDir
        if useabs:
            slndir = self.absSlnDir
        if useout:
            slndir = self.outSlnDir
        ret = str.replace(
              "$(SolutionDir)", slndir).replace(
              "$(ConfigurationName)", self.config.lower()).replace(
              "&quot;", "\"")
        if proj:
            ret = ret.replace("$(ProjectName)", proj.name)
            if proj.intdir != "":
                ret = ret.replace("$(IntDir)", proj.intdir)
            if proj.outdir != "":
                ret = ret.replace("$(OutDir)", proj.outdir)
        ret = ret.replace("\"", "")
        return ret

    def _getFileContent(self, fileName):
        """Try to open the file and return its contents. In case of error
        return None.
        
        Return the content of the file
        
        """
        try:
            file = open(fileName, 'rb')
            content = file.read()
            file.close()
        except:
            return None
        return content;

    def _relativePath(self, source, target):
        source = path.normpath(path.join(source.replace("\\.\\", "").replace("\\", "/"), "")).replace("\\", "/")
        target = path.normpath(path.join(target.replace("\\.\\", "").replace("\\", "/"), "")).replace("\\", "/")
        su = source.split("/")
        tu = target.split("/")
        su.reverse()
        tu.reverse()
        #remove parts which are equal   (['a', 'b'] ['a', 'c'] --> ['c'])
        while len(su) > 0 and len(tu) > 0 and su[-1] == tu[-1]:
            su.pop()
            last_pop=tu.pop()
        if len(su) == 1 and su[0] == "" and len(tu) == 0:
            #Special case: (http://foo/a/ http://foo/a -> ../a)
            su.append(last_pop)
            tu.append(last_pop)
        tu.reverse()
        relative_url = []
        for i in range(len(su)):
            relative_url.append("..")
        rel_url = path.normpath(string.join(relative_url + tu, "/"))
        return rel_url

    def _applyDirRepl(self, dirrepl, string):
        for rule in dirrepl:
            fr, to = rule
            string = string.replace(fr, to)
        return string

    def _applyLibRepl(self, librepl, string):
        for rule in librepl:
            fr, to = rule
            string = string.replace(fr, to)
        return string

    def _recursiveDep(self, proj, arrproj, dirrepl, librepl):
        # find dependant project
        depstr = ""
        for dep in proj.dependencies:
            for projdep in arrproj:
                if projdep.id == dep and projdep.outfile != "":
                    deptarget = path.basename(self._processMacros(projdep.outfile, projdep, False))
                    depstr = depstr + "'" + self._applyLibRepl(librepl, self._applyDirRepl(dirrepl, deptarget)) + "', " + self._recursiveDep(projdep, arrproj, dirrepl, librepl)
        return depstr

if __name__ == '__main__':
    # custom scripts
    exlist = []
    # special directory replacement rules
    dirrepl = []
    # special library name replacement rules (when win library name doesn't match OS's library name)
    librepl = []
    Sln2SCons("../winnt/test.sln", exlist, dirrepl, librepl, "../")

