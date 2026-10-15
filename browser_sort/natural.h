#ifndef ECHO_BROWSER_NATURAL_H
#define ECHO_BROWSER_NATURAL_H
/* Up to256 UTF16 units per name. Equal keys retain raw-index order externally.
 * ASCII/Latin-1 case insensitive; other code units retain deterministic order. */
int browser_natural_compare(const unsigned short *,const unsigned short *);
#endif
