#!/usr/bin/python2
import json, datetime, time, hashlib

import numpy
import scipy
import scipy.stats
import scipy.cluster
import scipy.cluster.vq


import logging
logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

THRESHOLD = 210
MIN_LEN = 3

def average(l):
    return sum(l) / len(l) if len(l) > 0 else None

class Event(object):
    def __init__(self, dt, typ, val):
        self.dt = dt
        self.typ = typ
        self.val = val

    def copy(self):
        return Event(self.dt, self.typ, self.val)

    def prototype(self):
        return Event(None, self.typ, self.val)

    def similar(self, other):
        return self.typ == other.typ and self.val == other.val

    def phash(self):
        return hashlib.sha256(json.dumps([self.typ, self.val]).encode('utf-8')).hexdigest()

    def getBucket(self):
        ''' Return a 2-tuple of (dow, hour) for the datetime. '''
        return self.dt.weekday(), self.dt.hour
    
    def pos(self):
        ''' Return the coordinate stat used for clustering. In this case, seconds since the beginning of the week. '''
        return self.dt.hour * 3600 + self.dt.minute * 60 + self.dt.second + self.dt.weekday() * 3600*24

    def __repr__(self):
        return "Event(dt=%r, typ=%r, val=%r)" % (self.dt, self.typ, self.val) 

    def __lt__(self, other):
        return self.typ < other.typ

class Cluster(object):
    def __init__(self, events, centroid):
        self.events = events
        self.centroid = centroid

    def __repr__(self):
        return "Cluster(events=%r, centroid=%r)" % (self.events, self.centroid)
    
    def range(self):
        a = [e.pos() for e in self.events]
        return max(a) - min(a) 
    
    def stderr(self):
        return numpy.std(numpy.array([e.pos() for e in self.events])) / numpy.sqrt(len(self.events))
    
    def center(self):
        return numpy.mean(numpy.array([e.pos() for e in self.events]))

    def centerTime(self):
        c = self.center()

        dow = int(c / (3600*24))
        c %= 3600*24

        hour = int(c / 3600)
        c %= 3600

        minute = int(c / 60)
        c %= 60

        second = int(c)

        return (dow, hour, minute, second)

    def __len__(self):
        return len(self.events)


if __name__ == '__main__': 
    from events import events

    eventGroups = {}
    for event in events:
        if event.phash() not in eventGroups:
            eventGroups[event.phash()] = []
        eventGroups[event.phash()].append(event)

    for eg in eventGroups.values():
        K_MIN = 1
        K_MAX = len(eg) / 3

        clusterSets = []

        for k in range(K_MIN, K_MAX):
            centroids, labels = scipy.cluster.vq.kmeans2(numpy.array([e.pos() for e in eg]), k, iter=200, minit='random')

            clusters = {}
            for eventIdx, centerIdx in enumerate(labels):
                if not centerIdx in clusters:
                    clusters[centerIdx] = Cluster(events=[], centroid=centroids[centerIdx])
                clusters[centerIdx].events.append(eg[eventIdx])

            clusters = list(clusters.values())

            clusterSets.append([cluster for cluster in clusters if len(cluster) > 1])

        # pick best cluster set
        bestClusterSet = None
        minAvgStdErr = None
        for clusters in clusterSets:
            stderr = average([cluster.stderr() for cluster in clusters if cluster.stderr() < THRESHOLD])
            if minAvgStdErr is None or stderr < minAvgStdErr:
                minAvgStdErr = stderr
                bestClusterSet = clusters

        clusters = bestClusterSet

        clusters.sort(key = lambda c: len(c))

        print '%s (%d total)' % (eg[0].prototype(), len(eg))
        for cluster in clusters:
            if len(cluster) > MIN_LEN and cluster.stderr() < THRESHOLD:
                print '\tCluster: n = %3d, u = %.2f, se = %.2f, r = %.2f; %s' % (len(cluster), cluster.center(), cluster.stderr(), cluster.range(), cluster.centerTime())










#def bucketToEnglish(bucket):
#    hour = bucket[1]
#    if hour == 12:
#        hourS = '12pm'
#    elif hour in (0, 24):
#        hourS = '12am'
#    elif hour < 12:
#        hourS = str(hour) + 'am'
#    else:
#        hourS = str(hour - 12) + 'pm'
#    return (['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][bucket[0]], hourS)
#
#def buildBucketList(events): # heh
#    bucketDict = {}
#    for event in events:
#        bucket = event.getBucket()
#        if bucket not in bucketDict:
#            bucketDict[bucket] = []
#        bucketDict[bucket].append(event)
#    return bucketDict
#
#def findCommon(bucketDict):
#    #numBuckets = 7 * 24 # should we use just numPopulatedBuckets here?
#    numBuckets = len(bucketDict) # just the populated buckets
#
#    avgCount = float(sum([len(lst) for lst in bucketDict.values()]))
#    avgCount /= numBuckets
#
#    logger.debug("Average bucket count: %s", avgCount)
#
#    avgCount += 2 # sue me
#
#    # apply the minimum threshold
#    avgCount = max(avgCount, MIN_THRESHOLD)
#
#    # group events by similar kind and by bucket
#    bucketHashes = {}
#    for events in bucketDict.values():
#        for event in events:
#            key = (event.getBucket(), event.phash())
#            if not key in bucketHashes:
#                bucketHashes[key] = []
#            bucketHashes[key].append(event)
#
#    res = []
#    for ((bucket, hsh), events) in bucketHashes.items():
#        event = events[0].prototype()
#        count = len(events)
#        res.append((count, bucket, event))
#
#    res.sort()
#    res.reverse()
#
#    for count, bucket, event in res:
#        if count > avgCount:
#            logging.info("%16s (%3d): %s", bucketToEnglish(bucket), count, event)
#
