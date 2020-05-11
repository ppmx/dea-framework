# Verification Process

## Checking Code
Statt `klee_assert()` sollten wir eigene Routinen schreiben. Hierfür bietet sich eventuell auch `void klee_warning(const char *message);` an.
Dies kommt aus dem Header [klee.h](https://github.com/klee/klee/blob/master/include/klee/klee.h).

### Beispiel
Wir haben 3 Funktionen mit den return Werten `ret_i` für `i \in {1,2,3}`. Der Verifcator Code sollte dann wie folgt aussehen:

```
if (ret_1 == ret_2 && ret1 != ret3)
    raise_error_and_abort("3 is failing")
    
if (ret1 == ret3 && ret1 != ret2)
    raise_error_and_abort("2 is failing")
    
if (ret2 == ret3 && ret2 != ret1)
    raise_error_and_abort("1 is failing")
```

Da wir allerdings die Äquivalenzklassen bilden wollen, führen wir folgenden Algorithmus ein:

### Clustering

Dieser Algorithmus bildet Cluster mit Libraries, die sich auf eine definierte Weise äquivalent sind. Die Definition
der Äquivalenz geschieht durch eine Funktion `eval(int a, int b)`, die zwei Indizes erhält und 0 zurück gibt, falls diese
Libs nicht äquivalent sind. Anderfalls gibt sie einen Wert ungleich 0 zurück. Die Cluster werden identifiziert durch einen
Index i und einer Zuweisung jeder Library zu einem Cluster (dies geschieht durch ein Array).

Hierbei gibt `n` die Anzahl der eingecheckten Libs an.

```
#define UNALLOCATED -1

/* Initialisierung
 *
 * Wir verwenden ein Array, um den Index des Clusters zu jeder Lib zu speichern.
 */
int mapping[n];

for (size_t i = 0; i < n; i++)
    mapping[i] = UNALLOCATED;

/* Hier starten wir das clustering.
 *
 * In der äußeren Schleife betrachten wir einmal jede Library, jeweils repräsentiert
 * durch den Inex i. Im Schleifenrump wollen wir für i eine Äquivalenzklasse festlegen.
 */
for (size_t i = 0; i < n; i++) {
    // Falls die betrachtete Lib bereits einer Klasse zugewiesen ist...
    if (mapping[i] != UNALLOCATED)
        continue;

    // Nun pruefen wir, ob j die Klasse fuer die Lib mit Index i sein kann
    for (size_t j = 0; j < n; j++) {
        if (j == i || mapping[j] == UNALLOCATED)
            continue;

        if (equal(i, j)) {
            mapping[i] = mapping[j];
            break;
        }
    }

    // An dieser Stelle gab es keine andere lib, die äquivalent zu lib[i] ist.
    // Somit bildet i an dieser Stelle seinen eigenen Cluster.
    if (mapping[i] == UNALLOCATED)
        mapping[i] = i;
}

// Falls es mehrere Cluster gibt, aborten wir. In Zukunft wollen wir hier die einzelnen Cluster reporten
for (size_t i = 1; i < n; i++) {
    if (mapping[0] != mapping[i]) {
        klee_assert(0);
    }
}
```

Anmerkung: der Algorithmus ist derzeit nicht optimiert in Laufzeit oder Speicherverwendung, wobei es derzeit (und vermutlich sowieso nicht) ein Problem darstellt.
