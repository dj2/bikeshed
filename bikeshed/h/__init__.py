from .dom import (
    E,
    addClass,
    addOldIDs,
    appendChild,
    appendContents,
    approximateLineNumber,
    childElements,
    childNodes,
    circledDigits,
    clearContents,
    closestAncestor,
    closestAttr,
    createElement,
    dedupIDs,
    emptyText,
    escapeAttr,
    escapeCSSIdent,
    escapeHTML,
    escapeUrlFrag,
    filterAncestors,
    find,
    findAll,
    fixSurroundingTypography,
    fixTypography,
    fixupIDs,
    foldWhitespace,
    hasAncestor,
    hasAttr,
    hasAttrs,
    hasChildElements,
    hasClass,
    hashContents,
    hasOnlyChild,
    headingLevelOfElement,
    innerHTML,
    insertAfter,
    insertBefore,
    isElement,
    isEmpty,
    isNormative,
    isOddNode,
    moveContents,
    nextSiblingElement,
    nextSiblingNode,
    nodeIter,
    outerHTML,
    parentElement,
    parseDocument,
    parseHTML,
    prependChild,
    previousElements,
    relevantHeadings,
    removeAttr,
    removeClass,
    removeNode,
    replaceAwkwardCSSShorthands,
    replaceContents,
    replaceMacros,
    replaceNode,
    replaceWithContents,
    safeID,
    scopingElements,
    sectionName,
    serializeTag,
    textContent,
    textContentIgnoringDecorative,
    treeAttr,
    unescape,
    unfixTypography,
    wrapContents,
)
from .serializer import Serializer
