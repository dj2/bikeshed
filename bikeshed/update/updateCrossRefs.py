# -*- coding: utf-8 -*-
from __future__ import division, unicode_literals
import io
import json
import re
import os
import urllib2
from collections import defaultdict
from contextlib import closing

from .. import config
from ..apiclient.apiclient import apiclient
from ..messages import *


anchorDataContentTypes = ["application/json", "application/vnd.csswg.shepherd.v1+json"]

def update(path, dryRun=False):
    try:
        say("Downloading anchor data...")
        shepherd = apiclient.APIClient("https://api.csswg.org/shepherd/", version="vnd.csswg.shepherd.v1")
        res = shepherd.get("specifications", anchors=True, draft=True)
        # http://api.csswg.org/shepherd/spec/?spec=css-flexbox-1&anchors&draft, for manual looking
        if ((not res) or (406 == res.status)):
            die("Either this version of the anchor-data API is no longer supported, or (more likely) there was a transient network error. Try again in a little while, and/or update Bikeshed. If the error persists, please report it on GitHub.")
            return
        if res.contentType not in anchorDataContentTypes:
            die("Unrecognized anchor-data content-type '{0}'.", res.contentType)
            return
        rawSpecData = res.data
    except Exception, e:
        die("Couldn't download anchor data.  Error was:\n{0}", str(e))
        return

    specs = dict()
    anchors = defaultdict(list)
    headings = defaultdict(dict)
    for rawSpec in rawSpecData.values():
        spec = genSpec(rawSpec)
        specs[spec['vshortname']] = spec
        specHeadings = headings[spec['vshortname']]

        def setStatus(obj, status):
            obj['status'] = status
            return obj
        rawAnchorData = (
            [setStatus(x, "snapshot") for x in linearizeAnchorTree(rawSpec.get('anchors', []))] +
            [setStatus(x, "current") for x in linearizeAnchorTree(rawSpec.get('draft_anchors', []))])
        for rawAnchor in rawAnchorData:
            rawAnchor = fixupAnchor(rawAnchor)
            linkingTexts = rawAnchor['linking_text']
            if linkingTexts[0] is None:
                # Happens if it had no linking text at all originally
                continue
            if len(linkingTexts) == 1 and linkingTexts[0].strip() == "":
                # Happens if it was marked with an empty lt and Shepherd still picked it up
                continue
            if 'section' in rawAnchor and rawAnchor['section'] == True:
                addToHeadings(rawAnchor, specHeadings, spec=spec)
            else:
                addToAnchors(rawAnchor, anchors, spec=spec)

    cleanSpecHeadings(headings)

    methods = extractMethodData(anchors)
    fors = extractForsData(anchors)

    if not dryRun:
        try:
            with io.open(os.path.join(path, "specs.json"), 'w', encoding="utf-8") as f:
                f.write(unicode(json.dumps(specs, ensure_ascii=False, indent=2, sort_keys=True)))
        except Exception, e:
            die("Couldn't save spec database to disk.\n{0}", e)
            return
        try:
            for spec, specHeadings in headings.items():
                with io.open(os.path.join(path, "headings", "headings-{0}.json".format(spec)), 'w', encoding="utf-8") as f:
                    f.write(unicode(json.dumps(specHeadings, ensure_ascii=False, indent=2, sort_keys=True)))
        except Exception, e:
            die("Couldn't save headings database to disk.\n{0}", e)
            return
        try:
            writeAnchorsFile(anchors, path)
        except Exception, e:
            die("Couldn't save anchor database to disk.\n{0}", e)
            return
        try:
            with io.open(os.path.join(path, "methods.json"), 'w', encoding="utf-8") as f:
                f.write(unicode(json.dumps(methods, ensure_ascii=False, indent=2, sort_keys=True)))
        except Exception, e:
            die("Couldn't save methods database to disk.\n{0}", e)
            return
        try:
            with io.open(os.path.join(path, "fors.json"), 'w', encoding="utf-8") as f:
                f.write(unicode(json.dumps(fors, ensure_ascii=False, indent=2, sort_keys=True)))
        except Exception, e:
            die("Couldn't save fors database to disk.\n{0}", e)
            return

    say("Success!")


def linearizeAnchorTree(multiTree, list=None):
    if list is None:
        list = []
    # Call with multiTree being a list of trees
    for item in multiTree:
        if item['type'] in config.dfnTypes.union(["dfn", "heading"]):
            list.append(item)
        if item.get('children'):
            linearizeAnchorTree(item['children'], list)
            del item['children']
    return list


def genSpec(rawSpec):
    spec = {
        'vshortname': rawSpec['name'],
        'shortname': rawSpec.get('short_name'),
        'snapshot_url': rawSpec.get('base_uri'),
        'current_url': rawSpec.get('draft_uri'),
        'title': rawSpec.get('title'),
        'description': rawSpec.get('description'),
        'work_status': rawSpec.get('work_status'),
        'working_group': rawSpec.get('working_group'),
        'domain': rawSpec.get('domain'),
        'status': rawSpec.get('status'),
        'abstract': rawSpec.get('abstract')
    }
    if spec['shortname'] is not None and spec['vshortname'].startswith(spec['shortname']):
        # S = "foo", V = "foo-3"
        # Strip the prefix
        level = spec['vshortname'][len(spec['shortname']):]
        if level.startswith("-"):
            level = level[1:]
        if level.isdigit():
            spec['level'] = int(level)
        else:
            spec['level'] = 1
    elif spec['shortname'] is None and re.match(r"(.*)-(\d+)", spec['vshortname']):
        # S = None, V = "foo-3"
        match = re.match(r"(.*)-(\d+)", spec['vshortname'])
        spec['shortname'] = match.group(1)
        spec['level'] = int(match.group(2))
    else:
        spec['shortname'] = spec['vshortname']
        spec['level'] = 1
    return spec


def fixupAnchor(anchor):
    '''Miscellaneous fixes to the anchors before I start processing'''

    # This one issue was annoying
    if anchor.get('title', None) == "'@import'":
        anchor['title'] = "@import"

    # css3-tables has this a bunch, for some strange reason
    if anchor.get('uri', "").startswith("??"):
        anchor['uri'] = anchor['uri'][2:]

    # If any smart quotes crept in, replace them with ASCII.
    linkingTexts = anchor.get('linking_text', [anchor.get('title')])
    for i,t in enumerate(linkingTexts):
        if t is None:
            continue
        if "’" in t or "‘" in t:
            t = re.sub(r"‘|’", "'", t)
            linkingTexts[i] = t
        if "“" in t or "”" in t:
            t = re.sub(r"“|”", '"', t)
            linkingTexts[i] = t
    anchor['linking_text'] = linkingTexts

    # Normalize whitespace to a single space
    for k,v in anchor.items():
        if isinstance(v, basestring):
            anchor[k] = re.sub(r"\s+", " ", v.strip())
        elif isinstance(v, list):
            for k1, v1 in enumerate(v):
                if isinstance(v1, basestring):
                    anchor[k][k1] = re.sub(r"\s+", " ", v1.strip())
    return anchor


def addToHeadings(rawAnchor, specHeadings, spec):
    uri = rawAnchor['uri']
    if uri[0] == "#":
        # Either single-page spec, or link on the top page of a multi-page spec
        heading = {
            'url': spec["{0}_url".format(rawAnchor['status'])] + uri,
            'number': rawAnchor['name'] if re.match(r"[\d.]+$", rawAnchor['name']) else "",
            'text': rawAnchor['title'],
            'spec': spec['title']
        }
        fragment = uri
        shorthand = "/" + fragment
    else:
        # Multi-page spec, need to guard against colliding IDs
        if "#" in uri:
            # url to a heading in the page, like "foo.html#bar"
            match = re.match(r"([\w-]+).*?(#.*)", uri)
            if not match:
                die("Unexpected URI pattern '{0}' for spec '{1}'. Please report this to the Bikeshed maintainer.", uri, spec['vshortname'])
                return
            page, fragment = match.groups()
            page = "/" + page
        else:
            # url to a page itself, like "foo.html"
            page, _, _ = uri.partition(".")
            page = "/" + page
            fragment = "#"
        shorthand = page + fragment
        heading = {
            'url': spec["{0}_url".format(rawAnchor['status'])] + uri,
            'number': rawAnchor['name'] if re.match(r"[\d.]+$", rawAnchor['name']) else "",
            'text': rawAnchor['title'],
            'spec': spec['title']
        }
    if shorthand not in specHeadings:
        specHeadings[shorthand] = {}
    specHeadings[shorthand][rawAnchor['status']] = heading
    if fragment not in specHeadings:
        specHeadings[fragment] = []
    if shorthand not in specHeadings[fragment]:
        specHeadings[fragment].append(shorthand)


def cleanSpecHeadings(headings):
    '''Headings data was purposely verbose, assuming collisions even when there wasn't one.
       Want to keep the collision data for multi-page, so I can tell when you request a non-existent page,
       but need to collapse away the collision stuff for single-page.'''
    for specHeadings in headings.values():
        for k, v in specHeadings.items():
            if k[0] == "#" and len(v) == 1 and v[0][0:2] == "/#":
                # No collision, and this is either a single-page spec or a non-colliding front-page link
                # Go ahead and collapse them.
                specHeadings[k] = specHeadings[v[0]]
                del specHeadings[v[0]]


def addToAnchors(rawAnchor, anchors, spec):
    anchor = {
        'status': rawAnchor['status'],
        'type': rawAnchor['type'],
        'spec': spec['vshortname'],
        'shortname': spec['shortname'],
        'level': int(spec['level']),
        'export': rawAnchor.get('export', False),
        'normative': rawAnchor.get('normative', False),
        'url': spec["{0}_url".format(rawAnchor['status'])] + rawAnchor['uri'],
        'for': rawAnchor.get('for', [])
    }
    for text in rawAnchor['linking_text']:
        if anchor['type'] in config.lowercaseTypes:
            text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        anchors[text].append(anchor)


def extractMethodData(anchors):
    '''Compile a db of {argless methods => {argfull method => {args, fors, url, shortname}}'''

    methods = defaultdict(dict)
    for key, anchors_ in anchors.items():
        # Extract the name and arguments
        match = re.match(r"([^(]+)\((.*)\)", key)
        if not match:
            continue
        methodName, argstring = match.groups()
        arglessMethod = methodName + "()"
        args = [x.strip() for x in argstring.split(",")] if argstring else []
        for anchor in anchors_:
            if anchor['type'] not in config.idlMethodTypes:
                continue
            if key not in methods[arglessMethod]:
                methods[arglessMethod][key] = {"args":args, "for": set(), "shortname":anchor['shortname']}
            methods[arglessMethod][key]["for"].update(anchor["for"])
    # Translate the "for" set back to a list for JSONing
    for signatures in methods.values():
        for signature in signatures.values():
            signature["for"] = list(signature["for"])
    return methods


def extractForsData(anchors):
    '''Compile a db of {for value => dict terms that use that for value}'''

    fors = defaultdict(set)
    for key, anchors_ in anchors.items():
        for anchor in anchors_:
            for for_ in anchor["for"]:
                if for_ == "":
                    continue
                fors[for_].add(key)
            if not anchor["for"]:
                fors["/"].add(key)
    for key, val in fors.items():
        fors[key] = list(val)
    return fors


def writeAnchorsFile(anchors, path):
    '''
    Keys may be duplicated.

    key
    type
    spec
    shortname
    level
    status
    url
    export (boolish string)
    normative (boolish string)
    for* (one per line, unknown #)
    - (by itself, ends the segment)
    '''
    groupedEntries = defaultdict(dict)
    for key,entries in anchors.items():
        group = config.groupFromKey(key)
        groupedEntries[group][key] = entries
    for group, anchors in groupedEntries.items():
        with io.open(os.path.join(path, "anchors", "anchors-{0}.data".format(group)), 'w', encoding="utf-8") as fh:
            for key, entries in sorted(anchors.items(), key=lambda x:x[0]):
                for e in entries:
                    fh.write(key + "\n")
                    for field in ["type", "spec", "shortname", "level", "status", "url"]:
                        fh.write(unicode(e.get(field, "")) + "\n")
                    for field in ["export", "normative"]:
                        if e.get(field, False):
                            fh.write("1\n")
                        else:
                            fh.write("\n")
                    for forValue in e.get("for", []):
                        if forValue:  # skip empty strings
                            fh.write(forValue + "\n")
                    fh.write("-" + "\n")
