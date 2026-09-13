Source URL: https://arxiv.org/abs/1906.09316
Fetched via: arXiv LaTeX source tarball -> pandoc, using this repo's .claude/skills/arxiv-doc-builder (convert_paper.py). Full text, not an abstract or summary.
Ingested: 2026-09-13
Document type: paper (arXiv preprint)
Title: Field Dependent Conductivity and Threshold Switching in Amorphous Chalcogenides - Modeling and Simulations of Ovonic Threshold Switches and Phase Change Memory Devices
License: arXiv distribution license (per-paper; not verified for redistribution beyond internal reference use)
Note: PDF, figures and LaTeX source were kept out of the repo (scratchpad only); this is the converted Markdown body only.

=== BEGIN CONVERTED FULL TEXT ===

---
title: ""
authors: "Tiffany McKerahan"
arxiv_id: "1906.09316"
version:
published:
primary_category:
categories: []
doi:
journal:
source_type: "pdf"
conversion_date: "2026-09-13T22:49:36.428431+00:00"
abstract:
---



<!-- Page 1 -->

© 2019 IEEE. Personal use of this material is permitted. Permission from IEEE must be obtained for all other uses, in any

current or future media, including reprinting/republishing this material for advertising or promotional purposes, creating new

collective works, for resale or redistribution to servers or lists, or reuse of any copyrighted component of this work in other

works.

<!-- Page 2 -->

Field Dependent Conductivity and Threshold

Switching in Amorphous Chalcogenides –

Modeling and Simulations of Ovonic Threshold

Switches and Phase Change Memory Devices

Jake Scoggin, Helena Silva, Senior Member, IEEE, and Ali Gokirmak, Senior Member, IEEE

devices can form undesirable current sneak paths between

selected and non-selected lines; hence access devices with non-

Abstract – We model electrical conductivity in metastable

amorphous Ge2Sb2Te5 using independent contributions from linear current-voltage (I-V) characteristics, high I on /I off ratios

temperature and electric field to simulate phase change memory (I /I ~106 for a 1000x1000 device array), and high drive

on off

devices and Ovonic threshold switches. 3D, 2D-rotational, and 2D

capabilities to write (I ~MA/cm2) are needed at each cross-

finite element simulations of pillar cells capture threshold write

point [5]. Ovonic threshold switches (OTS) made from

switching and show filamentary conduction in the on-state. The

model can be tuned to capture switching fields from ~5 to 40 MV/m amorphous chalcogenides are one such access device.

at room temperature using the temperature dependent electrical Amorphous chalcogenides are highly resistive under low

conductivity measured for metastable amorphous GST; lower and

electric fields and exhibit “threshold switching” to a highly

higher fields are obtainable using different temperature

dependent electrical conductivities. We use a 2D fixed out-of- conductive on-state at a threshold voltage (V th ). Once switched,

plane-depth simulation to simulate an Ovonic threshold switch in these materials remain in the on-state while a minimum holding

series with a Ge2Sb2Te5 phase change memory cell to emulate a

current or voltage (I or V ) is maintained (Fig. 2) [6].

crossbar memory element. The simulation reproduces the pre- hold hold

switching current and voltage characteristics found

experimentally for the switch + memory cell, isolated switch, and V 300 K

isolated memory cell. Device

Index Terms—Phase change memory, amorphous

semiconductors, finite element analysis R

I Load

I. INTRODUCTION

V Top

P app

HASE change memory (PCM) is a non-volatile memory that Electrode

stores information as the conductive crystalline or resistive

OTS Middle

amorphous phase of a material. The crystalline-to-amorphous

aGST Electrode

phase transition is controllable and reversib(lea,) with PC T M iN (e)

TiN

attaining 103x faster write times and 104x better endurance than PCM

cGST

flash memory [2]. PCM is CMOS back-end-of-line compatible,

45 nm

allowing memory integration on-chip with CMOS circuitry to

Bottom

eliminate latency from off-chip memory accessS [i3O]. PCM can

2 Electrode

be implemented as a crossbar array, allowing high device

(b) (f)

density (4F2) in multiple memory layers and efficient

neuromorphic computing [4]. Crossbars consist of

g 300 K g

perpendicular word and bit lines with n itle memory elements n itle

sandwiched between these lines at the crMoss-points (Fig. 1). M

Each word or bit line is connected to V dd o s u r ground through a Fig. 1: A schematic illustration of a cross-p s uoint cell with an Ovonic

o o

transistor, and cross-points can be rande

n

omly( c)accessed by threshold sw(igtc)h in series with a phase chane nge memory element. The

activating their corresponding word and bit e g lines. Non-selected shown cell structure is used for 2D analys e gis to compare modeling

o o

m results to the experimental results in [1]. r e

o te

H H

Submitted on XX/XX/XXXX. This work was supported by AFOSR MURI jacob.scoggin@uconn.edu; helena.silva@uconn.edu;

under Award No. FA9550-14-1-0351. ali.gokirmak@uconn.edu).

The authors are with the Department of Electrical and Computer

Engineering, University of Connecticut, Storrs, CT 06(2d69) USA (email: (h)

Crystal Orientation Liquid

10 nm

Amorphous

**Table 1:**

|  |
|---|
|  |



<!-- Page 3 -->

device thickness, suggesting a field-based mechanism at a

V (t)

(a) 3D (b) I app R Rot 2 a D ti o - nal threshold E th [15]. Theoretical arguments and the presence of

Load

crystalline filaments in failed devices suggest that on-state

eciv

conduction is filamentary [12], [15].

V

eD

r SiO2 1 µm Current-field (I-𝐸⃗ ) measurements on amorphous

chalcogenides typically show an ohmic regime at low 𝐸⃗ , an

1

intermediate regime where ln(𝐼)∝ 𝐸⃗ or 𝐸⃗ 2, and a high field

h = 50 nm

OTS regime where I increases at a super-exponential rate with 𝐸⃗

[20]. Reference [20] reviews conduction mechanisms in

amorphous materials and shows that multiple mechanisms can

h = 1 µm

TiN

fit measured data through the tuning of parameters which are

r = 100 nm

OTS otherwise difficult to validate (e.g. trap-to-trap distance,

effective carrier mass, and carrier mobility). Models for these

mechanisms have been proposed which define carrier

SiO TiN aGST

(c) 2 concentrations (n) and mobilities (μ) as functions of 𝐸⃗ and

22 1100 00 3D (~2 days) iii temperature (T) such that all three I-𝐸⃗ regimes are captured with

2D Rotational (~5 min) an electrical conductivity 𝜎 =𝑞𝑛𝜇, but such techniques are

iv ii

1100-3-3

computationally expensive in addition to relying on multiple

11

unknown fitting parameters. Reference [13] proposes a field-

1100-6-6 v based switching model where carrier concentrations rapidly

)A

)A

m 00 0

0

1

1

increase once trap states near the Fermi band are filled and fits

m

( I

(

I i the model to amorphous (a-) Ge 2 Sb 2 Te 5 (GST) measurements.

References [18], [19] propose a field-assisted thermal model

--11

2 based on multiple trap barrier lowering and fit the model to a-

33DD ((~~22 ddaayyss))

GeTe and doped a-GST measurements. References [14], [21]

--22 22DD -RRootta. t(i~o5n aml i(n~u5te ms)in)

ascribe switching to crystalline filaments which form under

--11..55 -1-1.0 --00..55 00.0 00..55 11.0 11..55 high 𝐸⃗ and fit the model to a-GST using relaxation oscillations.

1 VVdeDveivciece ( (VV)) They suggest that these filaments become unstable at low 𝐸⃗ in

OTS materials but remain stable in PCM materials.

Fig. 2: (a) 3D and (b) 2D-rotational OTS geometries used in this work.

T = 300 K is used as the initial condition and as the boundary condition Here, we model conductivity in a-GST as the sum of T and 𝐸⃗

at the top and bottom of the TiN contacts. (c) When a 3 V / 60 ns

dependent terms (σ = σ + σ ). This model does not require a

triangular pulse is applie ) Ad at V0 app, the device (i) is highly resistive until a T E

computationally expensive evaluation of the (density of states

Vswitch ~ 1.75 V, (ii) swimtches on in ~10 ps, (iii - iv) remains on until

the voltage and current (

I

drop below Vhold ~ 0.4 V and Ihold ~ 0.25 mA, × Fermi func tion) integral at every T, 𝐸⃗ combination where

and (v) returns to the high resistance off-state. Symmetric switching

conductivity is needed; hence, it is appropriate for transient

behavior is observed when a negative ramped pulse is applied. The 2D-

rotational and 3D simulatio-n1s give similar results, as expected for finite element simulations with dynamic T and 𝐸⃗ . While this

rotationally symmetric filamentary switching. Inset in (c) is the first model trades accuracy for ease of computation, simulations

quadrant in logarithmic scale.

show that it (i) can be tuned to fit a wide range of switching

Crystallization dynamics of these materials determine whether fields, (ii) captures the appropriate changes in threshold

they are more suitable fo-r2 an OTS or a PCM. PCM materials switching as we systematically vary ambient conditions,

include various stoichiometries of Ag-In-Sb-Te and Ge-Sb-Te, geometries, and the rise and fall times of applied pulses, and

with typical crystallization times on the order of 10 ns [7]. OTS (iii) can reproduce the behavior of a series PCM+OTS device

materials remain in their am-o1r.5phou-1s .0pha-s0e. 5duri0n.0g no0r.m5al 1.0when1 u.5sed with a finite element phase change model [22]–[25].

operation and are often characterized by the number of

V (V)

switching cycles they withstand before failure (tDhervioceugh, e.g., II. COMPUTATIONAL MODEL

material damage or crystallization): > 600 for GeTe [8], > 108 We use a-GST material parameters as in [23], [25] to simulate

6

for AsTeGeSiN [9], and unknown for As-doped Se-Ge-Si, a an OTS material. Of particular interest to this work is σ , which

a

material used in a commercial OTS+PCM crossbar array [10]. we model as in [26] and cap at σ = σ (930 K) (Fig. 3):

max T

There is still debate on the mechanism(s) underlying

𝜎 (𝑇,𝐸⃗ )=min( 𝜎 (𝑇)+𝜎 (𝐸⃗ ) , 𝜎 ), (1)

threshold switching despite many studies investigating this 𝑎 𝑇 𝐸 𝑚𝑎𝑥

phenomenon [1], [6], [19], [11]–[18]. V th scales linearly with which is equivalent to assuming that free carriers are excited to

**Table 1:**

| 1100 00 | 3D (~2 days)
2D Rotational (~5 |
|---|---|



<!-- Page 4 -->

T (K) dependent thermoelectric effects [34]:

400 600 800 T 1000

melt 𝑑𝑇

1- ( m ) a) 1 1 0 0 4 6  T (930 K)  T [28] [31] [30] 𝑑 𝑚 𝑐 𝑝 𝑑𝑡 ∇ − ⋅ ∇ 𝐽 ⋅ = (𝑘 𝛻 𝛻 ⋅ 𝑇 ( ) − = 𝜎𝛻 − 𝑉 𝛻 − 𝑉⋅ 𝜎 𝐽 𝑆 − 𝛻𝑇 𝛻 ) ⋅ = (𝐽 0 𝑆 𝑇)+𝑞 𝐻 ( ( 4 5 ) )

1-



(

102 [26]



E

w

th

h

er

e

m

re

a l

d

c

m

o n

is

d u

m

c

a

ti

s

v

s

i t

d

y,

e n

V

s

i

i

s

ty

e

,

l e

c

c

p

t r

i

i

s

c p

sp

o

e

te

c

n

if

t

i

i

c

a l,

h

J

e a

is

t,

c

t

u r

i

r

s

e n

ti

t

m

d

e

e

,

n s

k

i ty

is

,

100

[32] S is the Seebeck coefficient, and q accounts for the latent heat

H

10-2

0 25 50 E 75

of phase change. We use temperature dependent parameters for

th a-GST, crystalline GST (c-GST), TiN, and SiO as in [23], [25].

E (MV/m) 2

We model phase change as

(b)104

700 K

700 K

103 d𝐶⃗⃗⃗⃗𝐷⃗ =𝑁⃗⃗⃗⃗𝑢⃗⃗⃗𝑐⃗⃗⃗𝑙⃗𝑒⃗⃗⃗𝑎⃗⃗⃗𝑡⃗⃗𝑖⃗⃗𝑜⃗⃗𝑛⃗ +𝐺⃗⃗⃗⃗𝑟⃗⃗𝑜⃗⃗⃗𝑤⃗⃗⃗⃗𝑡⃗⃗ℎ⃗ +⃗𝑀⃗⃗⃗⃗𝑒⃗⃗⃗𝑙⃗𝑡 , (6)

1-m ) 102 dt

1- 101 [27]

where ⃗𝐶⃗⃗⃗𝐷⃗ is a 2-vector whose magnitude (CD) corresponds to

 ( 100 300 K 300 K T [1 h 1 is ] Work p w h h a o s s e e ( C o D ri e = n 0 ta o ti r o n 1 fo (θ r th ) e a c m o o rr r e p s h p o o u n s d o s r c to ry s g ta r l a l i i n n e o p r h i a e s n e t ) a t a i n o d n

10-1 CD

(tan(θ ) = CD /CD ), capturing nucleation, growth, and grain

0.0 0.5 1.0 1.5 CD 2 1

E/E (300 K) boundary melting [23], [25]. We solve for (6) in PCM devices

switch

but not OTS devices, which we assume do not crystallize in our

Fig. 3: (a) T and 𝐸⃗ dependent contributions to electrical conductivity

simulations.

in (1); temperature is uncertain for T > Tmelt. (b) Conductivity-Field

behavior using the model in this work (metastable a-GST) and the

III. SIMULATIONS

model in [19] (drifted, doped a-GST) at various temperatures. We use

Eswitch(300 K) = 25.01 MV / m in this work and Eswitch(300 K) = 155 We first simulate switching in 3D and 2D-rotational

MV/m for the curves in [19]. geometries by applying a 3V / 60 ns triangular pulse (Fig. 2a,b).

Results show filamentary switching with current confined to the

a band edge via independent thermal and electrical processes:

central portion of the device (Fig. 4a-j), with practically

𝜎 (𝑇,𝐸⃗ )=min( 𝑞(𝑛 +𝑛 )𝜇 , 𝜎 ), (2) identical I-V characteristics for 3D and 2D-rotational

𝑎 𝑇 𝐸 𝑚𝑎𝑥

simulations (Fig. 2c). 3D simulations show some instability of

where n and n are carriers excited via thermal or electrical

T E the filament location (slightly off-center in Fig. 4d,i) and

processes and 𝜇 is the free carrier mobility.

filament migration over time.

We fit σ to low-𝐸⃗ measurements of metastable a-GST wires

T We next evaluate the impact of σ by simulating switching

E

[27] and molten GST thin films [28], as described in [29] (Fig.

with σ = 0 (Fig. 5a) and compare the results with σ defined as

E E

3a). Measurements of liquid GST show a semiconductor-to-

in (3) (Fig. 5b). V and I are the values at which V

switch switch Device

metal transition near 930 K [30], with σ becoming practically

begins to decrease. Threshold switching occurs even with σ =

E

independent of T. We therefore limit σ a (T, 𝐸⃗ ) to σ T (930 K) = 0 due to thermal runaway. However, defining σ E as in (3) gives

4.1×105 [Ω-1 m-1], which is in line with the highest a switching field (E = V / h ) that is smaller and less

switch switch OTS

conductivities measured in molten GST [30]–[32](Fig. 3a). dependent on h (Fig. 5c). Some h dependence is still

OTS OTS

σ E is assumed to be an exponential which contributes 1% of observed due to changing thermal conditions.

σ T (300 K) at zero field and 10% of σ T (T melt ) at E th : Reference [33] reports switching fields from 8.1 MV/m (as-

deposited a-Ge Sb ) to 94 MV/m (as-deposited 4 nm thick a-

𝜎 (𝐸⃗ )= 𝜎𝑇(300 𝐾) exp(|𝐸⃗ |⋅𝐶 ) (3) 15 85

𝐸 100 1 Sb). We examine the tunability of our model by varying E th in

where C = 2.42×10-7 m/V is chosen such that σ (E ) = σ (T ) (3) from 5.6 to 560 MV/m (Fig. 6). Results show E switch varying

1 E th T melt

from 5 to 42.5 MV/m. E = 25.01 MV/m when E = 56

× 10%. We use E = 56 MV/m, the breakdown field measured switch th

th

MV/m, similar to the E = 28.75 MV/m measured in [13] for

in as-deposited a-GST [33], and T = 858 K [28] (Fig. 3a). switch

melt

melt-quenched a-GST. σ becomes negligible compared to σ

We include σ-𝐸⃗ curves at various temperatures calculated E T

when E > 200 MV/m even for high fields: the σ used in this

using the models in this work (for metastable a-GST) and the th T

work precludes E > 42.5 MV/m; a reduced σ is required

models in [19] (for drifted, doped a-GST) for comparison (Fig. switch T

for higher switching fields. I decreases by ~100x as V

3b). σ dominates at low fields, while σ begins to dominate at switch switch

T E

increases, resulting in a decrease in switching power (P )

higher and higher fields with increasing T. switch

from ~100 to 20 μW (Fig. 6c).

We couple heat transfer and current continuity physics to

simulate transient device operation, including temperature

<!-- Page 5 -->

(a) t- (b) t+ (c) t (d) t- (e) t+

switch switch peak hold hold

) A

102

(a) 3

4

) V

 (

( hctiw

S 101 1

2

V

hctiw

S

I

(f) (g) (h) (i) (j)

0

100

(b)

) W 75

2

2

00 n

(

m

k)

300 T (K) 950 ( 

P

hctiw

S 2

5

5

0

) A 0

m 1 107 108

(

I E (V/m)

Eth (V/m)

0 Threshold

Fig. 6: (a) The switching current (voltage) decreases (increases) and

(l) V

4 app (c) the switching power decreases with increasing Eth in (3). The device

) V switches thermally before the field contribution becomes significant

2

( V V for Eth > 1×108 V / m. As a result, further increases to Eth result in the

Device

0 same switching characteristics. (Fig. 2b: RLoad = 5 kΩ, hOTS = 100 nm,

0 t switch 50 t peak 100 t hold rOTS = 100 nm, Vapp = 5 V / 5 s triangular pulse).

time (ns)

V has been shown to decrease with increasing ambient

switch

temperature (T ), while the temperature behavior of I

Fig. 4: (a-e) x-y and (f-j) x-z temperature cut planes while switching ambient switch

the 3D OTS in Fig. 2a illustrate filamentary on-state conduction. (j) and P switch are less clear [19]. We simulate switching while

Current and (k) device voltage transients resulting from the applied varying T (the initial temperature and the fixed top and

ambient

Vapp used to generate the I-V in Fig. 2c. Superscripts “-” and “+” refer bottom TiN boundary temperatures, Fig. 2b) from 300 to 400 K

to the time steps (1 ns increments) before and after the subscripted (Fig. 7). V decreases as expected (Fig. 7a). I at first

switch switch

event. (Fig. 2a: RLoad = 1 k Ω, hOTS = 50 nm, rOTS = 100 nm, Vapp = 5 V

decreases and then increases with increasing T , while

ambient

/ 60 ns triangular pulse).

P monotonously decreases in the T range simulated

switch ambient

but is beginning to flatten with increasing T by 400 K.

(a) = 0 (b)  as in (3)

800 E E Next, we systematically vary r , h , and the rise time

OTS OTS

600 increasing h OTS (τ rise ) of V app in the geometry shown in Fig. 2b (Fig. 8). Results

) A agree with expected OTS behavior: V switch approximately

 400 increasing h doubles as h doubles [6], V decreases with increasing

( I OTS OTS switch

200 τ rise , approaching a minimum value [16], I hold and V hold are only

weakly dependent on h [15], and switching characteristics

0 OTS

are only weakly dependent on r due to filamentary

OTS

0 1 2 3 4 0 1 2 3 4

conduction in the on-state.

V (V) V (V)

Device Device Finally, we simulate an OTS and PCM in series (OTS+PCM,

Fig. 1) based on the devices fabricated and characterized in [1].

)m 60 (c)

/V  E = 0 We use a 2D, 45 nm fixed out-of-plane-depth simulation

M 40 instead of a 2D-rotational simulation to more appropriately

(

hctiw 20  as in (3) model phase change dynamics in the PCM with (6). We use a

ES

0

E

500 nm depth in the bit line to account for its large thermal mass

1.00  = 0 (Fig. 1), set T = 300 K as the initial and fixed TiN

E ambient

m n 52E

/h

h

c

c

t

t

i

i

w

w S

0

0

0

.

.

.

2

5

7

5

0

5 (d)



E

as in (3)

b

s

fo

q

o

r

u

u

a

t

n

h

r

d

e

e

a

r

p

r

m

y

u

a

l

t

s

l

e

i

e

z

m

a

(

p

t

1

i

e

o

n

r

n

a

s

t

(

u

r

s

i

r

t

s

e

a

e

s

r t

,

a

i

n

n

a

d

n

g

d

a

f a

t

r

l

e

F

l

s

i

t

e

g

i

t

m

.

t

1

e

h

s

e

a

)

n

d

a

d

e

t

v

e

V

n

ic

a

d

p

e

i

p

n

w

f

g

o

i

l

t

a

l

h

t

o

F

w

a

i

e

g

5

d

.

V

9

b

a

y

/

) .

1

5

W

μ

n

e

s

s

ES

0.00 then sweep V from 0 to 2.5 V over 50 ns to characterize the

app

25 50 75 100

OTS + reset PCM. We also simulate an isolated OTS and

h (nm)

OTS isolated reset PCM in the same way by replacing the PCM or

Fig. 5: The switching voltage increases with hOTS both (a) without and

OTS, respectively, with TiN (Fig. 9c,d). We plot the I-V

(b) with field dependent conductivity. Including field dependent

characteristics before switching, dividing currents and voltages

conductivity reduces the switching field’s (c) magnitude and (d)

by the isolated OTS I and V values in order to compare

sensitivity to hOTS. (Fig. 2b: RLoad = 5 kΩ, hOTS = 25 to 100 nm, rOTS = switch switch

100 nm, Vapp = 5 V / 5 s triangular pulse).

**Table 1:**

| (a) |
|---|
| (b) |

**Table 2:**

| (k) |
|---|
| (l) V
app
V
Device |

**Table 3:**

| (a) = 0
E
increasing h
OTS | (b)  as in (3)
E
increasing h
OTS |
|---|---|

**Table 4:**

| (c)
 = 0
E
 as in (3)
E |
|---|
|  = 0
E
(d)
 as in (3)
E |



<!-- Page 6 -->

(a) TiN (e)

3 aGST cGST TiN SiO

(a) 2

)

V (a) OTS+PCM (b) OTS (c) PCM

( 2

V

hctiw

S 1

[

T

[21

h

01

i

1]

s

6

W

G

o

a

r

l

k

lo] SiO 2

150 nm

(b) (f)

0

15 (b)

g g

) A

(



hctiw

1

5

0

1 T [2 h 0 i 0 s 9 W K o s u

n itle

Ma r u k ] (d O ) TS 1 1 [[ [ 52 2 ]0 0 0 0 9 9 K K a a u u ] ] O OP T TC S SM O

n itle

M s uTS

)W (  I hctiw

S

S 1 2 3 0 0 0 0 (c) S T O I / I hctiw S 0 0 o e n e g o m o H (c 1 S T O S T O I / I ) I / I hctiw S hctiw S 0 0

0

PT T Ch h iM i s s W 2 W o o r r k k

1

(g O )+ TS P P C C M M

2

P O P C o e n e g o re te H C + T + M M S

P 0 (d) 0 1 (h) 2

300 320 340 360 380 400 V / VO Sw T i S tch

V

V

/

/

V

V

O

O

STw

T

Si

S

tch

T Ambient (K) Fig. 9: (a) Reset OTS+PCM, (b) isolateSdw iOtchTS, and (c) isolated reset

Fig. 7: The (a) voltage, (b) current, and (c) power required to switch PCM. (d) Pre-switching I-V characteristics scaled by Vswitch and Iswitch

as the ambient temperature changes. Vswitch decreases monotonically, in the OTS using the model in this work (spheres) and experimental

but Iswitch and Pswitch have more complex relationships with Tambient. da

C

t

r

a

y

e

s

x

ta

t

l

r a

O

ct

r

e

ie

d

n

f

t

r

a

o

ti

m

o n

[1] (squ

L

a

iq

re

u

s

i

)

d

. I-V characteristics from this work

(Fig. 2b: RLoad = 5 kΩ, hOTS = rOTS = 100 nm, Vapp = 5 V / 5 s triangular show similar switching volt

A

ag

m

e

o

s

r

b

p

u

h

t

o u

lo

s

wer 1s0ca nlemd switching currents.

pulse). The schematic of the simulation setup is shown in Fig. 1. The

OTS+PCM reset animation for this simulation is available in

5 V / 10 ns 5 V / 100 ns 5 V / 1 s

supplementary material.

800

m

n

5 2

=

)A



4

6

0

0

0

0 between aGST and the (unreported) OTS material used in [1].

ST O ( I 200 IV. CONCLUSION

r

0

The coupling of thermal and electric field contributions to

m 800 electrical conductivity in amorphous semiconductors is

n 600

0

5

=

)A



400

c

p

o

ro

m

p

p

o

l

s

e

e

x

d

, a

t

s

o

e

e

v

x

id

p

e

la

n

i

c

n

e d

th

b

e

y

s

t

a

h

m

e

e

la r

c

g

h

e

a

n

ra

u

c

m

te

b

r

e

is

r

t i

o

c

f

s .

p h

O

y

u

si

r

c a

m

l

o

m

d

o

e

d

li

e

n

l

g

s

ST ( I 200

r O results show that threshold switching and ‘snap-back’ observed

0

h = 100 nm in OTS and PCM devices can be explained through electro-

m 800 OTS

n

0 0 1 )A 4

6

0

0

0

0

h

h

O

O

T

T

S

S

=

=

2

5

5

0

n

n

m

m t

f

h

il

e

a

r

m

m

e

a

n

l

t a

p

ry

h e

c

n

o

o

n

m

du

en

ct

a

i on

g i

a

v

n

in

d

g

c a

r

n

is e

b e

t

m

o

o

t

d

h

e

e

l

r

e

m

d

a

e

l

f fi

r

c

u

i

n

e

-

n

a

t

w

ly

a y

w it

a

h

n d

a

= ST (  I 200 finite element framework.

O

r 0

0 1 2 3 40 1 2 3 40 1 2 3 4 V. ACKNOWLDEGEMENTS

V (V) V (V) V (V)

Device Device Device The authors would like to thank Ilya Karpov of Intel

Fig. 8: Switching characteristics of OTS devices with varying radii, Corporation, Martin Salinga of RWTH Aachen University, Abu

ramp times, and heights. The simulated holding currents and voltages Sebastian of IBM Zurich, and Geoffrey Burr of IBM Almaden

are weakly dependent on hOTS, but the switching voltage ~doubles as for valuable discussions.

as hOTS doubles. (Geometry in Fig. 2b).

REFERENCES

our results to those presented in [1] (Fig. 9e). The results are

similar, with the OTS limiting the current in the reset PCM until

[1] D. Kau, S. Tang, I. V. Karpov, R. Dodge, B. Klehn, J. A. Kalb, J.

𝑉 / 𝑉𝑂𝑇𝑆 > 2 (Fig. 9d). This limits the current during Strand, A. Diaz, N. Leung, J. Wu, S. Lee, T. Langtry, K. W. Chang,

𝐷𝑒𝑣𝑖𝑐𝑒 𝑠𝑤𝑖𝑡𝑐ℎ

C. Papagianni, J. Lee, J. Hirst, S. Erra, E. Flores, N. Righos, et al.,

read in a reset cell while allowing high current in a set cell,

“A stackable cross point phase change memory,” in Technical

creating a large read margin. The smaller scaled currents for the Digest - International Electron Devices Meeting, IEDM, 2009, pp.

1–4 DOI:10.1109/IEDM.2009.5424263.

PCM and OTS+PCM in our simulation could be due to a

[2] F. Xia, J. Xiong, and N.-H. Sun, “A Survey of Phase Change

difference in the amorphous volume in the reset PCM; the fixed Memory Systems,” J. Comput. Sci. Technol., vol. 30, no. 1, pp.

out-of-plane depth in our simulations, which cannot capture 121–144, 2015 DOI:10.1007/s11390-015-1509-2.

[3] H.-S. P. Wong, S. Raoux, S. Kim, J. Liang, J. P. Reifenberg, B.

filaments smaller than 45 nm in depth and may thus Rajendran, M. Asheghi, and K. E. Goodson, “Phase

overestimate I in the OTS; or parameter differences ChangeMemory,” Proc. IEEE, vol. 98, no. 12, pp. 2201–2227, 2010

switch

**Table 1:**

| (a)
[[21011]6 Gallo]
This Work |
|---|
| (b)
1 [2
T
hctiw
S
T
(c) O I S
/
I |
| 0
0 |

**Table 2:**

| [2009 Kau]
[[52]009 Kau]
This Work
PTChiMs Work | OP TC SM
O T S O s uTS
(g)+ Oo e n T + S
OTS PCM e+
PgCM
PCM o
PC re M
te
H |
|---|---|

**Table 3:**

|  |  |  |
|---|---|---|
|  |  |  |
|  |  | h = 100 nm
OTS
h = 50 nm
OTS
h = 25 nm
OTS |



<!-- Page 7 -->

DOI:10.1109/JPROC.2010.2070050. [23] Z. Woods, J. Scoggin, A. Cywar, L. Adnane, and A. Gokirmak,

[4] A. Chen, Memory Selector Devices and Crossbar Array Design: A “Modeling of Phase-Change Memory: Nucleation, Growth, and

Modeling Based Assessment, vol. 16, no. 4. Springer US, 2017, pp. Amorphization Dynamics during Set and Reset: Part II - Discrete

1186–1200 DOI:10.1016/j.cub.2015.10.018. Grains,” IEEE Trans. Electron Devices, vol. 64, no. 11, pp. 4472–

[5] G. W. Burr, R. S. Shenoy, K. Virwani, P. Narayanan, A. Padilla, B. 4478, Nov. 2017 DOI:10.1109/TED.2017.2745500.

Kurdi, and H. Hwang, “Access devices for 3D crosspoint memory,” [24] J. Scoggin, R. S. Khan, H. Silva, and A. Gokirmak, “Modeling and

J. Vac. Sci. Technol. B, Nanotechnol. Microelectron. Mater. impacts of the latent heat of phase change and specific heat for

Process. Meas. Phenom., vol. 32, no. 4, p. 040802, 2014 phase change materials,” Appl. Phys. Lett., vol. 112, no. 19, p.

DOI:10.1116/1.4889999. 193502, 2018 DOI:10.1063/1.5025331.

[6] S. R. Ovshinsky, “Reversible electrical switching phenomena in [25] J. Scoggin, Z. Woods, H. Silva, and A. Gokirmak, “Modeling

disordered structures,” Phys. Rev. Lett., vol. 21, no. 20, pp. 1450– heterogeneous melting in phase change memory devices,” Appl.

1453, Nov. 1968 DOI:10.1103/PhysRevLett.21.1450. Phys. Lett., vol. 114, no. 4, pp. 1–6, Oct. 2019

[7] T. Matsunaga, J. Akola, S. Kohara, T. Honma, K. Kobayashi, E. DOI:10.1063/1.5067397.

Ikenaga, R. O. Jones, N. Yamada, M. Takata, and R. Kojima, “From [26] A. Faraclas, N. Williams, A. Gokirmak, and H. Silva, “Modeling of

local structure to nanosecond recrystallization dynamics in set and reset operations of phase-change memory cells,” IEEE

AgInSbTe phase-change materials,” Nat. Mater., vol. 10, no. 2, pp. Electron Device Lett., vol. 32, no. 12, pp. 1737–1739, Dec. 2011

129–134, 2011 DOI:10.1038/nmat2931. DOI:10.1109/LED.2011.2168374.

[8] M. Anbarasu, M. Wimmer, G. Bruns, M. Salinga, and M. Wuttig, [27] F. Dirisaglik, G. Bakan, Z. Jurado, S. Muneer, M. Akbulut, J. Rarey,

“Nanosecond threshold switching of GeTe 6 cells and their potential L. Sullivan, M. Wennberg, A. King, L. Zhang, R. Nowak, C. Lam,

as selector devices,” Appl. Phys. Lett., vol. 100, no. 14, 2012 H. Silva, A. Gokirmak, and others, “High speed, high temperature

DOI:10.1063/1.3700743. electrical characterization of phase change materials: metastable

[9] M. J. Lee, D. Lee, H. Kim, H. S. Choi, J. B. Park, H. G. Kim, Y. K. phases, crystallization dynamics, and resistance drift,” Nanoscale,

Cha, U. I. Chung, I. K. Yoo, and K. Kim, “Highly-scalable vol. 7, no. 40, pp. 16625–16630, Oct. 2015

threshold switching select device based on chaclogenide glasses for DOI:10.1039/C5NR05512A.

3D nanoscaled memory arrays,” Tech. Dig. - Int. Electron Devices [28] L. Adnane, N. Williams, H. Silva, and A. Gokirmak, “High

Meet. IEDM, no. December, pp. 10–13, 2012 temperature setup for measurements of Seebeck coefficient and

DOI:10.1109/IEDM.2012.6478966. electrical resistivity of thin films using inductive heating,” Rev. Sci.

[10] J. Choe, “Intel 3D XPoint Memory Die Removed from Intel Instrum., vol. 86, no. 10, p. 105119, Oct. 2015

OptaneTM PCM (Phase Change Memory),” Tech Insights, 2017. DOI:10.1063/1.4934577.

[Online]. Available: https://www.techinsights.com/about- [29] S. Muneer, J. Scoggin, F. Dirisaglik, L. Adnane, A. Cywar, G.

techinsights/overview/blog/intel-3D-xpoint-memory-die-removed- Bakan, K. Cil, C. Lam, H. Silva, and A. Gokirmak, “Activation

from-intel-optane-pcm/. [Accessed: 10-Dec-2018]. energy of metastable amorphous Ge2Sb2Te5 from room

[11] R. W. Pryor and H. K. Henisch, “Nature of the on-state in temperature to melt,” AIP Adv., vol. 8, no. 6, p. 065314, 2018

chalcogenide glass threshold switches,” J. Non. Cryst. Solids, vol. 7, DOI:10.1063/1.5035085.

no. 2, pp. 181–191, 1972 DOI:10.1016/0022-3093(72)90288-8. [30] R. Endo, S. Maeda, Y. Jinnai, R. Lan, M. Kuwahara, Y. Kobayashi,

[12] K. E. Petersen, “On state of amorphous threshold switches,” J. Appl. and M. Susa, “Electric resistivity measurements of Sb2Te3 and

Phys., vol. 47, no. 1976, p. 256, 1976 DOI:10.1063/1.322309. Ge2Sb2Te5 melts using four-terminal method,” Jpn. J. Appl. Phys.,

[13] D. Ielmini, “Threshold switching mechanism by high-field energy vol. 49, no. 6, p. 5802, 2010 DOI:10.1143/JJAP.49.065802.

gain in the hopping transport of chalcogenide glasses,” Phys. Rev. B [31] T. Kato and K. Tanaka, “Electronic Properties of Amorphous and

- Condens. Matter Mater. Phys., vol. 78, no. 3, pp. 1–8, Jul. 2008 Crystalline Ge Sb Te Films,” Jpn. J. Appl. Phys., vol. 44, no.

2 2 5

DOI:10.1103/PhysRevB.78.035308. 10, pp. 7340–7344, 2005 DOI:10.1143/JJAP.44.7340.

[14] M. Nardone, V. G. Karpov, D. C. S. S. Jackson, and I. V. Karpov, [32] K. Cil, F. Dirisaglik, and L. Adnane, “Electrical resistivity of liquid

“A unified model of nucleation switching,” Appl. Phys. Lett., vol. based on thin-film and nanoscale device measurements,” on

94, no. 10, pp. 10–12, Mar. 2009 DOI:10.1063/1.3100779. Electron Devices, 2013.

[15] W. Czubatyj and S. J. Hudgens, “Invited paper: Thin-film Ovonic [33] D. Krebs, S. Raoux, C. T. Rettner, G. W. Burr, M. Salinga, and M.

threshold switch: Its operation and application in modern integrated Wuttig, “Threshold field of phase change memory materials

circuits,” Electron. Mater. Lett., vol. 8, no. 2, pp. 157–167, 2012 measured using phase change bridge devices,” Appl. Phys. Lett.,

DOI:10.1007/s13391-012-2040-z. vol. 95, no. 8, pp. 1–4, 2009 DOI:10.1063/1.3210792.

[16] M. Wimmer and M. Salinga, “The gradual nature of threshold [34] G. Bakan, N. Khan, H. Silva, and A. Gokirmak, “High-temperature

switching,” New J. Phys., vol. 16, 2014 DOI:10.1088/1367- thermoelectric transport at small scales: Thermal generation,

2630/16/11/113044. transport and recombination of minority carriers,” Sci. Rep., vol. 3,

[17] A. Athmanathan, D. Krebs, A. Sebastian, M. Le Gallo, H. Pozidis, no. 1, p. 2724, 2013 DOI:10.1038/srep02724.

and E. Eleftheriou, “A finite-element thermoelectric model for

phase-change memory devices,” Int. Conf. Simul. Semicond. Jake Scoggin received his B.S. degree in

Process. Devices, SISPAD, vol. 2015–Octob, pp. 289–292, 2015 Nanosystems Engineering from Louisiana Tech

DOI:10.1109/SISPAD.2015.7292316. University in 2012 and his M.S. degree in Electrical

[18] M. Le Gallo, M. Kaes, A. Sebastian, and D. Krebs, “Subthreshold Engineering from Louisiana Tech University in

electrical transport in amorphous phase-change materials,” New J. 2014. He is a PhD student in Electrical & Computer

Phys., vol. 17, no. 9, 2015 DOI:10.1088/1367-2630/17/9/093035. Engineering at the University of Connecticut since

[19] M. Le Gallo, A. Athmanathan, D. Krebs, and A. Sebastian, 2014.

“Evidence for thermally assisted threshold switching behavior in

nanoscale phase-change memory cells,” J. Appl. Phys., vol. 119, no.

2, 2016 DOI:10.1063/1.4938532.

[20] M. Nardone, M. Simon, I. V. Karpov, and V. G. Karpov, “Electrical

conduction in chalcogenide glasses of phase change memory,” J. Helena Silva received her B.S. degree in Engineering

Appl. Phys., vol. 112, no. 7, 2012 DOI:10.1063/1.4738746. Physics from the University of Lisbon, Portugal in

[21] I. V. Karpov, M. Mitra, D. Kau, G. Spadini, Y. A. Kryukov, and V. 1998 and her M.S. and Ph.D. degrees in Applied

G. Karpov, “Evidence of field induced nucleation in phase change Physics from Cornell University in 2002 and 2005.

memory,” Appl. Phys. Lett., vol. 92, no. 17, pp. 4–6, 2008 She is currently an Associate Professor of Electrical

DOI:10.1063/1.2917583. and Computer Engineering at the University of

[22] Z. Woods and A. Gokirmak, “Modeling of Phase-Change Memory: Connecticut. Her research focuses on electronics

Nucleation, Growth, and Amorphization Dynamics During Set and devices for logic, memory, and energy conversion.

Reset: Part I—Effective Media Approximation,” IEEE Trans.

Electron Devices, vol. 64, no. 11, pp. 4466–4471, Nov. 2017

DOI:10.1109/TED.2017.2745506.

<!-- Page 8 -->

Ali Gokirmak received his B.S. degrees in Electrical

Engineering and Physics from University of

Maryland at College Park in 1998 and received his

Ph.D. in Electrical and Computer Engineering from

Cornell University in 2005. He joined the Electrical

& Computer Engineering Department of the

University of Connecticut in 2006, where he is

currently an associate professor .

---

## Notes

- This document was converted from PDF using pdfplumber
- Mathematical formulas are preserved from the PDF text layer
- Some formatting may require manual adjustment
- Complex equations may need to be formatted as LaTeX
- Please review and verify the content accuracy

