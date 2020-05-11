# Case: odd strcpy

Die zu Beginn generierten Testcases hatten lediglich als Assume ein `src[size - 1] = 0`.

Ich habe erwartet, hierbei `size` viele Pfade zu erhalten, da für strcpy entscheidend ist,
ob `src[i] = 0` für i < size. Ich wollte testen, ob es einen guten Unterschied macht, ob
ich annehme, dass `src[i] != 0` für i < size. Leider gab mir KLEE dann nur einen Pfad und einen
Fehler an, der ist `klee-output.md` zu entnehmen.

Mit ein wenig Debuggerei ging ich der Sache etwas nach und stellte fest, dass auch eine buggy Version
nicht als buggy erkannt wird.


## Lösungsansatz zur Erklärung der Fehlermeldung

Das Fast-Strcpy funktioniert so, dass in dem "fast" Teil nicht char's, sondern Wörter kopiert werden.
Dies funktioniert in drei Schritten:

1. Es werden die Bytes einzeln kopiert, die bis zu einem Wort-Align der Adresse liegen
2. Dann werden solange Wörter gelesen, bis zu dem Wort, das als nächstes kopiert werden soll und ein Nullbyte enthält
3. Ab dann werden wieder, bis zum Nullbyte, bytes kopiert, um nicht Daten, die hinter dem Nullbyte liegen aber noch im Worteinzug sind, zu leaken

Nun meldet KLEE einen Fehler in dem Prozess, da im zweiten Schritt Wörter gelesen werden. Nun werden unter Umständen auch Bytes
des Wortes gelesen, die außerhalb unseres Buffers liegen.


Visualisierung des Szenarions, wo out-of-bound-reads (mit Wortgröße = 8 Bytes) geschehen:

```

Leserichtung: ––>

   |xxxxxxxx|xxxxxxxx|xxxxxxxx|xxxyyyyyy|
––––––––––––––––––––––––––––––––––––––––––––
...|????????|????????|????????|??0      |...
––––––––––––––––––––––––––––––––––––––––––––

```

Hierbei markiert `x` die Bereiche, die Teil des Buffers sind. Somit ist der Buffer 27 Bytes groß. Die `?` markieren,
dass die entsprechende Speicherzelle mit einem Wert ungleich 0 gefüllt sein kein. Nun liest die fast-strcpy Implementation
im word-copy-Schritt im letzten Wort nicht nur die Zellen, die mit `x` markiert wurde, sondern auch die, die mit `y`
markiert wurde. Das bemerkt KLEE und meldet diesen Fehler.

