#!/usr/bin/env python3
# Copyright Andrea Di Iorio
# This file is part of FFmpegFastTrimConcat
# FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFmpegFastTrimConcat is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Flexible concatenation of videos by script generation for ffmpeg
to support re encodingless video concat videos are groupped by common metadata with FlexibleGroupByFields function
groupped video items can be segmentated randomically or procedurally with a flexible config (remove start / end / rnd seg)
    segment generation is configured by a (copy of) struct named SegGenOptionsDflt
    seg generation can be graphically visualized with _debug_graph_turtle_segments function
actual segment trim will be realized with a script (dflt genSegs.sh) using ffmpeg -ss -to (see lambdas for alternative cutting methods )
segments can be merged together with either ffmpeg concat filter or concat demuxer
    ( the former require re encoding, NB with large num of segments is aggressive on mem usage )
good try of concat demuxer vids groupping is excluding ["duration","bit_rate","nb_frames","tags","disposition","avg_frame_rate","color"] -
_________________________________________________________________
ENV OVERRIDE OPTION
ENCODE: str for encode out video (dflt Nvidia h264 in FFmpegNvidiaAwareEncode)
DECODE: str for decode in video (dflt Nvidia h264 in FFmpegNvidiaAwareDecode)
FFMPEG: target ffmpeg build to use (dflt Nvidia builded one )
"""
from configuraton import *
from copy import deepcopy
from os import environ as env
import argparse
from random import random, randint, shuffle
from collections import namedtuple
from MultimediaManagementSys import *
from scriptGenerator import FFmpegTrimConcatFlexible, FFmpegConcatFilter, buildFFMPEG_segExtractPreciseNoReencode, buildFFMPEG_segExtractNoReencode

if not DISABLE_GUI:    from GUI import *
### Vid Seg Cutting Flexible
# constr specification
SegGenOptionsDflt = {"segsLenSecMin": None, "segsLenSecMax": None, "maxSegN": 1, "minStartConstr": 0,"maxEndConstr": None}

def GenVideoCutSegmentsRnd(item, segGenConfig=SegGenOptionsDflt, MORE_SEGN_THREASHOLD_DUR_SEC=596):
    """
    generate random segment identified by start/end time point as [(s1Start,s1End),(s2Start,s2End),...]
    multiple segment will be allocated in different portions of the vid
    @param item:
    @param segGenConfig: segment generation configuration with these fields
        -minStartConstr maxEndConstr identify respectivelly constraint in start/end time in item vid duraion for each segments,
          maxEndConstr may be specified also as a negative time, the abs will be subtracted to the itemduration
          these constraint are ignored if not applicable (start after the end || end > item duration)
        -minSegLen/maxSegLen -> min/max segment len, if None -> it will be set to max allowable duration
    @param MORE_SEGN_THREASHOLD_DUR_SEC: threshold of duration, above witch will be selected to cut maxSegN segments
    @return: list of [(startSegSec,endSegSec),...]
    """
    #### get seg gen option in vars
    maxEndConstr = segGenConfig["maxEndConstr"]
    minStartConstr = segGenConfig["minStartConstr"]
    maxSegN = segGenConfig["maxSegN"]
    minSegLen = segGenConfig["segsLenSecMin"]
    maxSegLen = segGenConfig["segsLenSecMax"]
    duration = item.duration
    assert duration > 0 and minStartConstr >= 0, "invalid config"
    ## time constraint in segment in cut
    if duration > minStartConstr: duration -= minStartConstr  # remove first part to skip
    if maxEndConstr != None:
        if maxEndConstr > 0 and maxEndConstr < duration:
            duration = maxEndConstr - minStartConstr
        elif maxEndConstr < 0 and duration + maxEndConstr > 0:
            duration += maxEndConstr  # negative end constr
    # if max/min seg len is None => get the full possible duration [NB pre costrained ]
    if maxSegLen == None: maxSegLen = duration
    if minSegLen == None: minSegLen = duration

    nSeg = randint(1, maxSegN)
    if MORE_SEGN_THREASHOLD_DUR_SEC > 0 and duration >= MORE_SEGN_THREASHOLD_DUR_SEC: nSeg = maxSegN
    # gen random segs inside solts of time each with lenght = totDur/nSeg
    outSegs = list()  # list of [(startSegSec,endSegSec),...]
    segmentSlotLen = float(duration) / nSeg
    if minSegLen > segmentSlotLen: print("bad config, minSegLen > seg slot len, decresing to 3");minSegLen = 3
    if maxSegLen > segmentSlotLen: print(
        "bad config, maxSegLen > seg slot len, decresing to slot len");maxSegLen = segmentSlotLen
    slotStart = minStartConstr
    for x in range(nSeg):  # segment times genration in different slots NB minMax SegLen has to be setted correctly
        segLen = (random() * (maxSegLen - minSegLen)) + minSegLen
        # actual seg start rnd placed in the avaible space of the curr slot
        segStart = slotStart + random() * (segmentSlotLen - segLen)
        ###alloc generated segment
        segEndOut = segStart + segLen
        outSegs.append((segStart, segEndOut))
        slotStart += segmentSlotLen
    return outSegs


def _select_items_group(items, keyGroup):
    global SelectedGroupK
    SelectedGroupK = keyGroup

# ExcludeGroupKeys=["bit_rate","nb_frames","tags","disposition","has_b_frame","avg_frame_rate","color"]
# excludeGroupKeys=["rate","tags","disposition","color","index","refs"]

def argParseMinimal(args):
    # minimal arg parse use to parse optional args
    parser = argparse.ArgumentParser(
        description=__doc__+'\ngroup Video for concat flexible\n concat generated segments from groupped videos')
    parser.add_argument("pathStart", type=str, default=".", help="path to start recursive search of vids")
    parser.add_argument("--maxEndConstr", type=float, default=None, help="costum max end allowable for segments")
    parser.add_argument("--minStartConstr", type=float, default=None, help="costum min start allowable for segments")
    parser.add_argument("--segsLenSecMax", type=int, default=None, help="")
    parser.add_argument("--segsLenSecMin", type=int, default=None, help="")
    parser.add_argument("--maxSegN", type=int, default=None, help="")
    parser.add_argument("--groupSelectionMode", type=str,
                        choices=["GUI_TUMBNAIL_SELECT", "TAKE_ALL_MOST_POPOLOUS","MULTI_GROUPS","GROUPS_ITEMS","ALL_MERGED"], default="GROUPS_ITEMS",
                        help="mode of selecting groups to concat: GUI_TUMBNAIL_SELECT -> select item via avaible tumbnails in gui module\n"
                             "TAKE_ALL_MOST_POPOLOUS -> take the most popolouse group,\nMULTI_GROUPS -> select multiple groups to apply segmnta. & concat separatelly\n ALL_MERGED -> operate on all founded items"
                             "GROUPS_ITEMS -> select groups to applay segmnt. & concat togheter")
    # parser.add_argument("--grouppingRule",type=str,default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()),help="groupping mode of items")
    parser.add_argument("--concurrencyLev", type=int, default=2,
                        help="concurrency in cutting operation (override env CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS)")
    parser.add_argument("--groupDirect", type=bool, default=False,
                        help="group metadata founded by direct groupping keys embedded in code")
    parser.add_argument("--groupFiltering", type=str, default=None,choices=["len","dur","both"],help="filtering mode of groupped items: below len or duration threshold the group will be filtered away")
    parser.add_argument("--justFFmpegConcatFilter", type=bool, default=False,
                        help="concat selected items with ffmpeg's concat filter")
    parser.add_argument("--genGroupFilenames", type=int, choices=[0, 1, 2], default=0,
                        help="gen newline separated list of file paths for each founded group: 0=OFF,1=ON,2=JUST GEN groupFnames, no segmentation, cumulative time is logged before each file path with a line starting with #")
    parser.add_argument("--shuffle", type=bool, default=True,help="shuffle order of item concat")
    return parser.parse_args(args)


if __name__ == "__main__":
    nsArgParsed = argParseMinimal(argv[1:])
    segGenConfig = deepcopy(SegGenOptionsDflt)
    for k in SegGenOptionsDflt.keys():
        if k not in nsArgParsed: continue
        opt = nsArgParsed.__dict__[k]
        if opt != None: segGenConfig[k] = opt
    # env override
    selectTargetItems = "TAKE_ALL_MOST_POPOLOUS"
    startPath = nsArgParsed.pathStart
    Take = nsArgParsed.groupSelectionMode
    GUI_SELECT_GROUP_ITEMS = True  # if ITERATIVE_PLAY_CONFIRM: select group on gui
    ### getting items
    startPath = [startPath]
    if PATH_SEP in nsArgParsed.pathStart: startPath = nsArgParsed.pathStart.split(PATH_SEP)
    mItemsDict, grouppingsOld = dict(), dict()
    for path in startPath:
        mItemsDict = GetItems(path, mItemsDict, True)
    items=FilterItems(mItemsDict.values())
    ### GROUP VIDEOS BY COMMON PARAMS IN METADATA
    #either group excluding some metadata field, or group by specific field (groupDirect)
    excludeOnKeyList, wildcardMatch = True, True
    groupFields = ExcludeGroupKeys
    if nsArgParsed.groupDirect:
        excludeOnKeyList, wildcardMatch = False, False
        groupFields = GroupKeys
    grouppings = dict() #groupKey -> items
    for i in items:     #classify each item with a group key
        groupK=GroupByMetadataValuesFlexible(i, groupFields, excludeOnKeyList, wildcardMatch)
        if groupK not in grouppings: grouppings[groupK]=list()
        grouppings[groupK].append(i)
    ####### ORGANIZE GROUPS

    if nsArgParsed.groupFiltering != None:
        groupFilteringBasis=nsArgParsed.groupFiltering
        minSize = MIN_GROUP_LEN
        if nsArgParsed.groupFiltering == "dur": minSize = MIN_GROUP_DUR
        if nsArgParsed.groupFiltering == "both":minSize = min(MIN_GROUP_DUR,MIN_GROUP_LEN)
        grouppings= FilterGroups(grouppings, minSize, nsArgParsed.groupFiltering)
    itemsGroupped = list(grouppings.items())
    itemsGroupped.sort(key=lambda x: len(x[1]),reverse=True)
    assert len(itemsGroupped) > 0, "filtered all groups,change groupping params"
    ###WRITE GROUPS IN LIST FILES
    if nsArgParsed.genGroupFilenames != 0:  # build group filename listing if requested
        groupFileLinePrefix = GENGROUPFILENAMESPREFIX
        for i in range(len(itemsGroupped)):
            groupID, itemsList = itemsGroupped[i]
            if nsArgParsed.shuffle: shuffle(itemsList)
            outGroupFileName = "group_" + str(i) + ".list"
            file = open(outGroupFileName, "w")
            file.write("#" + str(groupID) + "\n")
            durCumul = 0
            for item in itemsList:
                file.write("#startAtSec:\t" + str(durCumul) + "\tfor: " + str(item.duration) + "\n")
                file.write(groupFileLinePrefix + " " + item.pathName + "\n")
                durCumul += item.duration
            file.close()
    if nsArgParsed.genGroupFilenames == 2: exit(0)  # asked to exit after group file generation
    mostPopolousGroup, mostPopolousGroupKey = itemsGroupped[0][1], itemsGroupped[0][0]

    ### SELECT TARGET GROUPPABLE ITEMS
    selectedGroups=list()           #groups list to applay segs & concat separatelly
    if Take == "GROUPS_ITEMS":
        if not DISABLE_GUI:         selection = guiMinimalStartGroupsMode(grouppings, trgtAction=SelectWholeGroup)
        else:                       selection = selectGroupTextMode(grouppings)
    elif Take == "MULTI_GROUPS":
        #if not DISABLE_GUI:         selection = guiMinimalStartGroupsMode(grouppings, trgtAction=SelectWholeGroup) #TODO GUI
        selectedGroups = selectGroupTextMode(grouppings,joinGroupItems=False)
    elif Take == "GUI_TUMBNAIL_SELECT":
        assert not DISABLE_GUI,"not avaible gui"
        selection = guiMinimalStartGroupsMode(grouppings)
        print(selection)
    elif Take == "ALL_MERGED":
        selection = items
    else:   #TAKE_ALL_MOST_POPULOSE
        selection= mostPopolousGroup
    if len(selectedGroups)==0: selectedGroups=[selection]   #populate target group if not selected multi groups
    #### SEGMENTIZE AND CONCAT SELECTED ITEMS
    if nsArgParsed.shuffle:
        for g in selectedGroups:    shuffle(g)
    for g in range(len(selectedGroups)):
        bash_batch_segs_gen, concat_filter_file, concat_filelist_fname = BASH_BATCH_SEGS_GEN + str(g), \
                                                                         CONCAT_FILTER_FILE + str(g), \
                                                                         CONCAT_FILELIST_FNAME + str(g)
        if nsArgParsed.justFFmpegConcatFilter:
            FFmpegConcatFilter(selectedGroups[g], concat_filter_file)
        else:
            FFmpegTrimConcatFlexible(selectedGroups[g],GenVideoCutSegmentsRnd ,SEG_BUILD_METHOD=buildFFMPEG_segExtractNoReencode,
                                     segGenConfig=segGenConfig, \
                                     BASH_BATCH_SEGS_GEN=bash_batch_segs_gen,
                                     CONCAT_FILELIST_FNAME=concat_filelist_fname, CONCAT_FILTER_FILE=concat_filter_file)
