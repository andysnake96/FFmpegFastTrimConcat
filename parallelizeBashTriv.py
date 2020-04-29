#!/usr/bin/env python3
#Copyright Andrea Di Iorio
#This file is part of FFmpegFastTrimConcat
#FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#FFmpegFastTrimConcat is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.
#

"""
parallelize an omogenous bash script adding at range of lines & and adding a bash wait every Concurrency lines
output script placed in same src script folder with <Concurrency>_parallelized.sh
"""
from sys import argv
#parse args
if len(argv) < 2:
        print("usage <omogenous bash script path to parallelize, [CONCURRENCY LEVEL (dflt 3)] [START END lineNum to parallelize (dflt 0 0 as the whole file )]>")
        print(__doc__)
        exit(1)
Concurrency=3
if len(argv) == 3: Concurrency=int(argv[2])
startL,endL=0,0
if len(argv) == 5: startL,endL=int(argv[3]),int(argv[4])
srcScriptPath=argv[1]
dstScriptPath=srcScriptPath+str(Concurrency)+"_parallelized.sh"

outLines=list()
bashLines=open(srcScriptPath).readlines()
if endL<=0: endL=len(bashLines)+endL         #handle negative last line number
for i in range(startL,endL):
    if i!=0 and i % Concurrency ==0: outLines.append("wait\n")
    outLines.append(bashLines[i][:-1]+" &\n")
if outLines[-1]!="wait\n": outLines.append("wait\n")    #last line assure is a wait
#write modded lines
open(dstScriptPath,"w").writelines(outLines)
