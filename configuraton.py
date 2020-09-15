from os import environ as env
GENGROUPFILENAMESPREFIX="file "
TMP_SEL_FILE="/tmp/selection.tmp.list.json"
######
### INTERNAL CONFIGURATION PARAMS
# vid files handled extensions
IMG_TUMBRL_EXTENSION = "jpg"
VIDEO_MULTIMEDIA_EXTENSION = ["mp4", "wmw"]
METADATA_EXTENSION = "json"
# pool workers
POOL_TRESHOLD = 100
if "POOL_TRESHOLD" in env: POOL_TRESHOLD = int(env["POOL_TRESHOLD"])
POOL_SIZE = 4
if "POOL_SIZE" in env: POOL_SIZE = int(env["POOL_SIZE"])
# var
MIN_GROUP_DUR=120
if "MIN_GROUP_DUR" in env: MIN_GROUP_DUR= int(env["MIN_GROUP_DUR"])
MIN_GROUP_LEN=4
if "MIN_GROUP_LEN" in env: MIN_GROUP_LEN= int(env["MIN_GROUP_LEN"])
DISABLE_GUI = False
if "DISABLE_GUI" in env and "T" in env["DISABLE_GUI"].upper(): DISABLE_GUI = True
if not DISABLE_GUI:  # try to enable GUI importing GUI module (with its tkinter dependencies ...)
    try:
        from GUI import *
    except Exception as e:
        print("not importable GUI module", e)
        DISABLE_GUI = True
NameIdFirstDot = True  # IF TRUE the nameID will be extracted from a path name up to the first founded dot
if env.get("NameIdFirstDot") != None and "F" in env["NameIdFirstDot"].upper(): NameIdFirstDot = False
#export comma separated list of keyword to filter away items after a scan
FilterKW=[]
if env.get("FilterKW") != None: FilterKW=env["FilterKW"].split(",") 
FORCE_METADATA_GEN = True  # force the generation of metadata of each founeded vid without a matching metadata file
if env.get("FORCE_METADATA_GEN") != None and "F" in env[
    "FORCE_METADATA_GEN"].upper(): FORCE_METADATA_GEN = False

# ITERATIVE_TRIM_SELECT mode out filenames
SELECTION_FILE = "selection.list.json"
TRIM_RM_SCRIPT = "trimReencodingless.sh"
### CONCAT SEGS
CONCAT_FILELIST_FNAME,BASH_BATCH_SEGS_GEN,CONCAT_FILTER_FILE="concat.list","genSegs.sh","CONCAT_FILTER_FILE"
# GROUP KEYS--------------------------
GroupKeys = ["width", "height", "sample_aspect_ratio"]
# groupKeys=["duration"]
# ECLUDE KEYS-------------------------
# excludeGroupKeys=["bit_rate","nb_frames","tags","disposition","avg_frame_rate","color","index"]
ExcludeGroupKeys = ["duration", "bit_rate", "nb", "tag", "disposition", "has", "avg", "col", "refs", "index"]
PATH_SEP = ":"
FFmpegNvidiaAwareDecode = " -vsync 0 -hwaccel cuvid -c:v h264_cuvid "
FFmpegNvidiaAwareEncode = " -c:v h264_nvenc "
FFmpegNvidiaAwareEncode += " -preset fast -coder vlc "
FFmpegDbg = " -hide_banner -y -loglevel 'error' "
FFmpegNvidiaAwareBuildPath = "/home/andysnake/ffmpeg/bin/nv/ffmpeg_g " + FFmpegDbg
FFmpegBasePath = "~/ffmpeg/bin/ffmpeg "
FFMPEG = FFmpegNvidiaAwareBuildPath
### Env override config
Encode = FFmpegNvidiaAwareEncode
Decode = FFmpegNvidiaAwareDecode
if env.get("ENCODE") != None: Encode = env("ENCODE")
if env.get("DECODE") != None: Decode = env("DECODE")
if env.get("FFMPEG") != None: FFMPEG = env("FFMPEG")
