#include <string.h>
#include <stdint.h>
#include <limits.h>
#include "libc.h"

#define ALIGN (sizeof(size_t))
#define ONES ((size_t)-1/UCHAR_MAX)
#define HIGHS (ONES * (UCHAR_MAX/2+1))
#define HASZERO(x) ((x)-ONES & ~(x) & HIGHS)

char *__stpcpy(char *restrict d, const char *restrict s)
{
	size_t *wd;
	const size_t *ws;

	// Falls s und d bezüglich sizeof(size_t) gegeneinander aligned sind:
	if ((uintptr_t)s % ALIGN == (uintptr_t)d % ALIGN) {
		// s und d inkrementieren, solange s nicht auf sizeof(size_t) aligned ist:
		for (; (uintptr_t)s % ALIGN; s++, d++)
			// Kopiere dieses eine byte und falls es null ist, returne
			// btw: return d wäre für strcpy() falsch, allerdings returned strcpy() auch
			// nicht den Rückgabewer von stpcpy()
			if (!(*d=*s)) return d;

		wd=(void *)d; ws=(const void *)s;

		// an dieser Stelle werden dann Wörter kopiert und abgebrochen, falls in diesem Wort
		// ein Nullbyte war
		for (; !HASZERO(*ws); *wd++ = *ws++);

		d=(void *)wd; s=(const void *)ws;
	}
	for (; (*d=*s); s++, d++);

	return d;
}

weak_alias(__stpcpy, stpcpy);
