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
thread T2:
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P01-O1` | `T2.r1 = 1` |
| `P01-O2` | `x = 0` |

## P02

```
thread T1:
  ST x 1
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P02-O1` | `T1.r1 = 0` |
| `P02-O2` | `T1.r1 = 1` |

## P03

```
thread T1:
  ST x 1
  FENCE
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P03-O1` | `T1.r1 = 0` |
| `P03-O2` | `T1.r1 = 1 and x = 1` |

## P04

```
thread T1:
  ST x 1
  ST y 2
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P04-O1` | `T1.r1 = 0` |
| `P04-O2` | `T1.r1 = 1` |

## P05

```
thread T1:
  ST x 1
  ST y 2
  ST z 3
  LD r1 x
  LD r2 z
```

| Observation | Claim |
|---|---|
| `P05-O1` | `T1.r1 = 0` |
| `P05-O2` | `T1.r1 = 1 and T1.r2 = 0` |

## P06

```
thread T1:
  ST x 1
  LD r1 x
  ST x 2
```

| Observation | Claim |
|---|---|
| `P06-O1` | `T1.r1 = 0 and x = 1` |
| `P06-O2` | `T1.r1 = 0 and x = 2` |

## P07

```
thread T1:
  ST x 1
  LD r1 y
thread T2:
  ST y 1
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P07-O1` | `T1.r1 = 0 and T2.r1 = 0` |
| `P07-O2` | `x = 0` |

## P08

```
thread T1:
  ST x 1
  FENCE
  LD r1 y
thread T2:
  ST y 1
  FENCE
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P08-O1` | `T1.r1 = 0 and T2.r1 = 0` |
| `P08-O2` | `T1.r1 = 0 and T2.r1 = 1` |

## P09

```
thread T1:
  ST x 1
  ST y 1
thread T2:
  LD r1 y
  LD r2 x
```

| Observation | Claim |
|---|---|
| `P09-O1` | `T2.r1 = 1 and T2.r2 = 0` |
| `P09-O2` | `T2.r1 = 0 and T2.r2 = 1` |

## P10

```
thread T1:
  ST x 1
  ST y 2
thread T2:
  ST y 1
  ST x 2
```

| Observation | Claim |
|---|---|
| `P10-O1` | `x = 1 and y = 1` |
| `P10-O2` | `x = 2 and y = 2` |

## P11

```
thread T1:
  ST x 1
  LD r1 x
  LD r2 y
thread T2:
  ST y 2
  ST x 2
```

| Observation | Claim |
|---|---|
| `P11-O1` | `T1.r1 = 1 and T1.r2 = 0 and x = 1` |
| `P11-O2` | `T1.r1 = 2 and T1.r2 = 2` |

## P12

```
thread T1:
  ST x 1
  LD r1 x
thread T2:
  ST x 2
  LD r1 x
```

| Observation | Claim |
|---|---|
| `P12-O1` | `T1.r1 = 2 and T2.r1 = 1` |
| `P12-O2` | `T1.r1 = 1 and T2.r1 = 2 and x = 1` |

## P13

```
thread T1:
  ST x 1
  LD r1 x
  LD r2 y
thread T2:
  ST y 1
  LD r1 y
  LD r2 x
```

| Observation | Claim |
|---|---|
| `P13-O1` | `T1.r1 = 1 and T1.r2 = 0 and T2.r1 = 1 and T2.r2 = 0` |
| `P13-O2` | `T1.r1 = 1 and T1.r2 = 0 and T2.r1 = 1 and T2.r2 = 1` |

## P14

```
thread T1:
  ST x 1
  LD r1 x
  LD r2 y
thread T2:
  ST y 2
  ST y 3
  ST x 2
```

| Observation | Claim |
|---|---|
| `P14-O1` | `T1.r1 = 1 and T1.r2 = 0 and x = 1` |
| `P14-O2` | `T1.r1 = 1 and T1.r2 = 2 and x = 2` |

## P15

```
thread T1:
  ST x 1
  CAS r1 x 1 2
```

| Observation | Claim |
|---|---|
| `P15-O1` | `T1.r1 = 0` |
| `P15-O2` | `T1.r1 = 1 and x = 2` |

## P16

```
thread T1:
  ST x 1
thread T2:
  LD r1 x
  LD r2 x
```

| Observation | Claim |
|---|---|
| `P16-O1` | `T2.r1 = 1 and T2.r2 = 0` |
| `P16-O2` | `T2.r1 = 0 and T2.r2 = 1` |
