
from utils import to_tuple
from configuration import *

### Items Groupping Functions: Vid -> groupKey string
def GroupByMetadataValuesFlexible(item, groupKeysList, excludeOnKeylist=False, wildcardFieldMatch=True):
    """
    classify a Vid item by its metadata associating to it a key that can be used to group omogeneous vids togheter (FFmpeg concat demuxer , concatFilter)
    if EXCLUDE_ON_KEYLIST is true the categorization will be based on values of all fields not in groupKeysList
        so groupKeysList  will act as a black list actually
    returned group Key for the item as a list of pairs MetadataFieldKey->(item metadata val on that fild)
    @param item:                Vid obj with metadata to classify
    @param groupKeysList:       list of metadatas field to use to classify the vid.
        either field to use (whitlist) or not to use among all (blacklisting)
    @param excludeOnKeylist:  if true the given fields at @param groupKeysList will be used as blacklist,
        all other field will be used to classify the vid
    @param wildcardFieldMatch:    if True the given groupKeyList's field will as a pattern to match among all metadata field of item
    @return: immutable key based on the other params, builded with all used metadata field-value pairs
    """
    assert item.metadata!=None,"missing metadata for groupping"
    groupKeysList.sort()
    vidStreamMetadata = item.metadata[0]  # get video stream of vid obj.metadata (in metadata read is guarantied the vid stream is at the 0th pos)
    outK = list()  #metadata field-value pairs used to classify item
    vidStreamAllKeys = list(vidStreamMetadata.keys())
    vidStreamAllKeys.sort()
    for field in vidStreamAllKeys:
        if excludeOnKeylist:      #groupKeyList is a blacklist of field for classification
            if wildcardFieldMatch:
                skipField = False
                for k in groupKeysList:
                    if k in field:
                        skipField = True
                        break
                if not skipField:           outK.append((field, vidStreamMetadata[field]))
            else:                   #match the full fields in groupKeysList
                if field not in groupKeysList:  outK.append((field, vidStreamMetadata[field]))
        else:
            if wildcardFieldMatch:
                keepField=False
                for k in groupKeysList:
                    if k in field:
                        keepField=True
                        break
                if keepField:   outK.append(field)
            else:
                if field in groupKeysList: outK.append((field, vidStreamMetadata[field]))
    groupK = to_tuple(outK)
    hash(groupK)
    return groupK

### managment groupping functions
def sizeBatching(item,groupByteSize=(100*(2**20))): 
    #group by size in batch of 500MB(dflt) each
    return str(groupByteSize/2**20)+"MB_Group:\t"+ str(item.sizeB // groupByteSize)
def durationBatching(item,groupMinNum=5):
    #group by duration in batch of 5 min(dflt) each
    return str(groupMinNum*(item.duration // (60*groupMinNum)))+" ~Min_Group"

def ffprobeExtractResolution(item):                 #just get resolution  +SAR
    return str(item.metadata[0]["width"])+" X "+str(item.metadata[0]["height"])+" SAR "+str(item.metadata[0]["sample_aspect_ratio"])

def ffmpegConcatDemuxerGroupping(items):
    #try to group items on common metadata values (expressed field to not consider)
    #may be suitable for the ffmpeg's concat demuxer
    return GroupByMetadataValuesFlexible(items,ExcludeGroupKeys,\
        excludeOnKeylist=True,wildcardFieldMatch=True)

def ffmpegConcatFilterGroupping(items):
    #try to group items on common metadata values 
    #may be suitable for the ffmpeg's concat filter
    return GroupByMetadataValuesFlexible(items,GroupKeys,\
        excludeOnKeylist=False,wildcardFieldMatch=False)

#dict of groupFuncName -> groupFunc
GrouppingFunctions={ f.__name__ : f for f in [ffprobeExtractResolution,ffmpegConcatDemuxerGroupping,sizeBatching,durationBatching]}
