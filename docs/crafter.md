# Crafter Process

## Intro

The crafter is a framework to generate programs, each calling a test harness which is defined
by the related test. The program also includes every blob that is defined in the
crafter configuration. The challenge here is to generate the test harness and to call the proper
functions that are renamed for each library. In the end, we want to generate one blob which can be used
as input for a testing engine like KLEE or AFL.

## Configuration

```
{
	"libs": ["libA", "libB", "libC"]
	"klee_headers": "./path/to/klee-include"
}
```


## Needed Headerfiles
You have to serve the KLEE headers. Download them and configure the correct path.
