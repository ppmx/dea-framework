## Wird `diet_strcpy()` zuerst gecallt, dann:

```
bd2b5ef39858:/reports/standalone/strcpy1 $ klee strcpy.bc 
KLEE: output directory is "/reports/standalone/strcpy1/klee-out-1"
KLEE: Using STP solver backend
KLEE: WARNING ONCE: function "__pthread_self" has inline asm
KLEE: WARNING ONCE: function "a_ctz_64" has inline asm
KLEE: WARNING ONCE: function "__pthread_self13" has inline asm
KLEE: WARNING ONCE: function "a_ctz_6431" has inline asm
KLEE: WARNING: executable has module level assembly (ignoring)
KLEE: ERROR: /home/mx/work/RESEARCH/sputnik/code/libs/diet/dietlibc-0.33/lib/strcpy.c:27: memory error: out of bound pointer
KLEE: NOTE: now ignoring this error at this location

KLEE: done: total instructions = 109
KLEE: done: completed paths = 1
KLEE: done: generated tests = 1
```


## Wird `musl_strcpy()` zuerst gecallt, dann:

```
bd2b5ef39858:/reports/standalone/strcpy1 $ klee strcpy.bc 
KLEE: output directory is "/reports/standalone/strcpy1/klee-out-0"
KLEE: Using STP solver backend
KLEE: WARNING ONCE: function "__pthread_self" has inline asm
KLEE: WARNING ONCE: function "a_ctz_64" has inline asm
KLEE: WARNING ONCE: function "__pthread_self13" has inline asm
KLEE: WARNING ONCE: function "a_ctz_6431" has inline asm
KLEE: WARNING: executable has module level assembly (ignoring)
KLEE: ERROR: /home/mx/work/RESEARCH/sputnik/code/libs/musl/musl-1.1.19/src/string/stpcpy.c:20: memory error: out of bound pointer
KLEE: NOTE: now ignoring this error at this location

KLEE: done: total instructions = 128
KLEE: done: completed paths = 1
KLEE: done: generated tests = 1
```

## Wird meine eigene Implementation `best_strcpy()` zuerst gecallt:

... dann kommt einer der Fehler von oben. Meine wirft also keinen Fehler. :-)
