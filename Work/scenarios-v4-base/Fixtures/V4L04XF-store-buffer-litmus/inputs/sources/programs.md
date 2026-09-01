# Litmus programs and observations

Instruction syntax and machine semantics: `machine-spec.md` (same
directory). Registers are per thread; `Tn.rk = c` in an observation
claims the FINAL value of register `rk` of thread `Tn` in a complete
run; a bare `v = c` claims the final shared-memory value of `v`. An
observation holds only if ALL of its claims hold simultaneously in
the same complete run.

Classify every observation ID on both machines (see `task.md`).

## P01

```
thread T1:
  ST x 1
  ST y 2
  LD r1 x
  STR p r1
thread T2:
  LD r2 p
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P01-O1` | `T1.r1 = 0 and T2.r2 = 0 and p = 0` |
| `P01-O2` | `T2.r2 = 1 and T2.r3 = 0` |

## P02

```
thread T1:
  ST x 1
  ST y 2
  ST z 3
  LD r1 x
  STR p r1
thread T2:
  LD r2 p
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P02-O1` | `T1.r1 = 0` |
| `P02-O2` | `T2.r2 = 1 and T2.r3 = 1` |

## P03

```
thread T1:
  ST x 1
  LD r1 x
  STR e r1
  LD r2 y
thread T2:
  ST y 2
  ST x 2
```

| Observation | Claim |
|---|---|
| `P03-O1` | `e = 1 and T1.r2 = 0 and x = 1` |
| `P03-O2` | `e = 0` |

## P04

```
thread T1:
  ST x 1
  LD r1 x
  LD r2 y
thread T2:
  ST y 2
  CAS r3 x 0 2
```

| Observation | Claim |
|---|---|
| `P04-O1` | `T1.r1 = 1 and T1.r2 = 0 and T2.r3 = 1 and x = 2` |
| `P04-O2` | `T1.r1 = 1 and T1.r2 = 0 and T2.r3 = 1 and x = 1` |

## P05

```
thread T1:
  ST x 1
  ST f 1
thread T2:
  LD r1 f
  ST g 1
thread T3:
  LD r2 g
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P05-O1` | `T2.r1 = 1 and T3.r2 = 1 and T3.r3 = 0` |
| `P05-O2` | `T2.r1 = 0 and T3.r2 = 1 and T3.r3 = 1` |

## P06

```
thread T1:
  CAS r1 x 0 1
thread T2:
  CAS r1 x 0 2
```

| Observation | Claim |
|---|---|
| `P06-O1` | `T1.r1 = 1 and T2.r1 = 1` |
| `P06-O2` | `T1.r1 = 1 and T2.r1 = 0 and x = 1` |

## P07

```
thread T1:
  ST x 1
  ST y 1
  LD r1 x
thread T2:
  CAS r2 x 0 5
  LD r3 y
```

| Observation | Claim |
|---|---|
| `P07-O1` | `T1.r1 = 5` |
| `P07-O2` | `T1.r1 = 5 and T2.r3 = 1 and x = 5` |

## P08

```
thread T1:
  ST x 1
  FENCE
  LD r1 y
thread T2:
  ST y 1
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P08-O1` | `T1.r1 = 0 and T2.r1 = 0` |
| `P08-O2` | `T1.r1 = 1 and T2.r1 = 0` |

## P09

```
thread T1:
  ST x 1
  ST y 2
  ST z 3
  CAS r1 w 0 1
thread T2:
  CAS r2 w 0 1
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P09-O1` | `T1.r1 = 1 and T2.r2 = 0 and T2.r3 = 0` |
| `P09-O2` | `T1.r1 = 0 and T2.r2 = 1 and T2.r3 = 0` |

## P10

```
thread T1:
  ST x 1
  ST x 2
  LD r1 x
thread T2:
  LD r2 x
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P10-O1` | `T1.r1 = 1` |
| `P10-O2` | `T2.r2 = 2 and T2.r3 = 1` |

## P11

```
thread T1:
  ST x 1
  ST y 1
  ST z 1
  LD r1 z
  LD r2 x
thread T2:
  LD r3 z
  LD r4 x
```

| Observation | Claim |
|---|---|
| `P11-O1` | `T1.r1 = 0 and T1.r2 = 1` |
| `P11-O2` | `T2.r3 = 0 and T2.r4 = 1` |

## P12

```
thread T1:
  ST x 1
  LD r1 x
  LD r2 y
thread T2:
  ST y 2
  FENCE
  ST x 2
```

| Observation | Claim |
|---|---|
| `P12-O1` | `T1.r1 = 1 and T1.r2 = 0 and x = 1` |
| `P12-O2` | `T1.r1 = 2 and T1.r2 = 0` |

## P13

```
thread T1:
  ST x 7
  CAS r1 f 0 1
thread T2:
  CAS r2 f 1 2
  LD r3 x
```

| Observation | Claim |
|---|---|
| `P13-O1` | `T2.r2 = 1 and T2.r3 = 0` |
| `P13-O2` | `T2.r2 = 1 and T2.r3 = 7 and f = 2` |

## P14

```
thread T1:
  ST x 1
  ST x 2
  ST x 3
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P14-O1` | `T1.r1 = 1` |
| `P14-O2` | `T1.r1 = 3` |

## P15

```
thread T1:
  ST x 1
  ST a 1
thread T2:
  ST y 1
  ST b 1
thread T3:
  LD r1 a
  LD r2 y
  LD r3 b
  LD r4 x
```

| Observation | Claim |
|---|---|
| `P15-O1` | `T3.r1 = 1 and T3.r2 = 0 and T3.r3 = 1 and T3.r4 = 0` |
| `P15-O2` | `T3.r1 = 1 and T3.r2 = 0 and T3.r3 = 1 and T3.r4 = 1` |

## P16

```
thread T1:
  ST x 1
  ST y 1
  LD r1 x
  STR z r1
thread T2:
  LD r2 z
  LD r3 y
```

| Observation | Claim |
|---|---|
| `P16-O1` | `T2.r2 = 0 and T2.r3 = 1 and z = 0` |
| `P16-O2` | `T2.r2 = 1 and T2.r3 = 0` |

## P17

```
thread T1:
  ST x 1
  LD r1 x
  FENCE
  LD r2 x
thread T2:
  ST x 2
```

| Observation | Claim |
|---|---|
| `P17-O1` | `T1.r1 = 0 and T1.r2 = 1 and x = 2` |
| `P17-O2` | `T1.r1 = 2 and T1.r2 = 2 and x = 1` |

## P18

```
thread T1:
  ST x 1
  ST y 1
  ST x 2
  LD r1 y
thread T2:
  LD r2 x
  LD r3 y
```

| Observation | Claim |
|---|---|
| `P18-O1` | `T1.r1 = 0` |
| `P18-O2` | `T2.r2 = 0 and T2.r3 = 1` |

## P19

```
thread T1:
  ST x 1
  ST y 1
thread T2:
  LD r1 y
  FENCE
  LD r2 x
```

| Observation | Claim |
|---|---|
| `P19-O1` | `T2.r1 = 1 and T2.r2 = 0` |
| `P19-O2` | `T2.r1 = 0 and T2.r2 = 1` |

## P20

```
thread T1:
  ST x 1
  ST x 2
thread T2:
  ST x 3
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P20-O1` | `T2.r1 = 3 and x = 1` |
| `P20-O2` | `T2.r1 = 1 and x = 3` |
