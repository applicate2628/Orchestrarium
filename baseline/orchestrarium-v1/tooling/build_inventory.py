#!/usr/bin/env python3
"""Execute the reviewed inventory implementation embedded in this frozen entrypoint."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import zlib
from pathlib import Path

FROZEN_PATH = "baseline/orchestrarium-v1/tooling/build_inventory.py"
SOURCE_PATH = "scripts/baseline/build_inventory.py"
SOURCE_BLOB = "563760d3a494dcd761c7d0d91b84769e03c5354e"
MATERIALIZATION = "git-cat-file-reviewed-tree-blob"
SOURCE_MATERIALIZATION = "embedded-reviewed-source-blob"
SOURCE_B85 = (
    'c-rMVZExE+(%=0nxax;mJzHtI&m9ha-~+PV^e#ZR4eE4(gCC!wNL0*?Ecx`3#OM0IKQlv8BqcdX_r4r(1?ouTa5x;!8;7G;Kb$mG'
    'd2%E26Q19*?XF%I`Hv&d^L}bXmav4^yxfRfRJDlNqK<Akd&@+A&-1z{1+Q3Ilq|}b*le0Qy2&{EtEkycRPjvYJQ$6x)|}n)oR<*{'
    'U?q=|iq+6o@_#nGs(C^KikshfTr&V#^Ah?2BLY1X<(<fHSzU5IVO7DRkwy&&Hj&6H_`5BOq=^Mi9;HAp%Od=Zi_J#VRlqK4#_?%3'
    '8ckUoZKE5JiF!BH%h(0KRYg8y{GOLPm@A6!fUJy1Dcb@;6Tp<$0Lc<@3nasG6IL~48pZs70b>nq&)`Z0(AMM$t_`586ZRnLHSsMM'
    'wTLoU1<oLfoNb~lV%6)MZlYYIFi0UbjF#&=LEbQt;OKfsv=vRgZ8WtNBCDFsCIZ?v$&5v8-2l!hZiU9PjbgKD$kC##Veif#VQb#9'
    '4Uh8frahFR<|px*$9I4|jyX?w5-=KZ3aet%sqEYo36~f~l3*MyDXdshinL~FS!@WsD{Uo5hQanLwC@xl!0IRy$w=h5N-2KD76lC0'
    '7iA~>9=Q?oX#`|dAfb`Snvw_X5`I}#Cz-ejP{c<gnmG*9riQLC1m@z(0byR$gsvKmbX$45jmnDa_jOdQ0g-;i&C$<ArJt(i280u-'
    'Xj^veW6d{P6bwm4Tx1!j0M4n&cwaOicctt{Nrd@y-z5nquIRF;#3Q~+xO%rmjZt8~L|c5Fum$cMFl97ay#L$zFK6Me=U)~VpFgoV'
    'J01Oe{^9KF$E)zm`Q_)u#ntC8e}`rdhGrrLReJZQcYi+lT*7`<Akd{~Hs0v-*Q?8~SK+6#U(Oc*JRULl=N(lpZz2H(bVYX!3%u?%'
    '5)3W=Xf%qm2=?|uqdG6kq8xt#hKUWQ7k?&4dfr0nOH=W33QCLYX=S~og>f7dkXVcop0coP^6*yFV^oK*EQ)%jxc&xYp_+jtl@r*+'
    'M`*t(iVV1LRW{sb)4yOB`^Ii|uv|$+$*U%-0mMi|0Qe=_@ZZvdsXT>yHEG-9hh*LoV46XSL5JoRw#$plbEhBHbG#qPp5u=-6RPX{'
    'LzGoqHv04{Qbl|KCaNj(81?ywIeR<nOa_Znfa)Da;tY%fMz<?SIHDPQO`T5v467#IS91?mnt@gI{1$f^2^ihk<`kL5_OIFN;I~5L'
    'W8|5CAVue3;r414*afj2`v-+i(r-}$9BlWRS4DQuLusP=TVC>%Hk@|1Znha;()Pp8N-{!@#2v27abI>O3>J4kB@+S*_NG&C5F*{d'
    'bL#B@{ox<`y~J?<f_+Uq;U*LR`!Fk%fE<wkYSzK6xFX>uG?ivb26i~ahCV+exM2x`E?vIZKLVWRH}<K>`AV^?j2>V`q#;HL+Qqdk'
    'lER+&lVWGp6p8aX&C{~i@~>XYG;OkMc=$9c^4m_U;*QfsDrBjPQ5pG58v@e!9jpP4ELSu*rC2F0$^?BWFe|9Q7}w()@BiL<zEM5U'
    'F>qB1bk?C6Y+>GTqx0p?h1l>KLV!A&-~=H$7}8-xWu`-;bn3g~KzAo9WDCLHm=}@2s>Hu|NQysiXJ{2Zs$wBLU!nIHApg-tuE|go'
    '9W@mYfR)89cqd+g*Rf3onIs?rupnEJM;1-s*ruMeNx=GX+hfM_$Cz(xHvTor8tF<V>}xKN4Cz={R3VVd%p-;>rdUD>14FB&q*iYk'
    '+slU^O3->42?6Sn;RXs(0InE<q48LTqtEl-w?#0hAQBkg@!dR&HaAJcAadKx=y&;c<yZkZz!=3S2_@#LZvxsW!4>N00wsJ!20;ZL'
    'Qsgb^Cym!epveV{Llm%As3+q@#C3pN0CKCbnL;l}Iy2XgUPACU;7Nh?^%UbPX%ugwI$nD(@~k3%(y{(-$1B$WVGD=IOn1|KOjM-D'
    'D6dC=VAdBvk>Bk=sU4g#WbUyI0haC$qn?>SJJjw1nj*7huJ}943FvfSwlCnhqyFp<3@l6D(ODNonl;sW>_V(TAUOsaE?)u^RE*|2'
    ';L144Q7*YhHI^a^EjbKNAPKwSzy_{#1fxehaL5Cz#O)1{3FfP;QB>t?P)e^W7v9=e=JjaKK$>k7J{qlebh5LXm!~W2xbZfks(>o*'
    'g)5Z7lcHaZ1vAuc*5M@-K>+yUi|1={{<sC?z)FX^YGc@5K9C9Qcz)zKPspx0_Re-PHf2Lj;E0*mJ`xZ1gAzr9I&Ou-ER@I?9&tLz'
    'IyDP%jc9`L2Gb97sSGb>XAMyj9?Lr1gb;QMheu92dwe@JPs!D{?Cm;eXNWQ&OAU|4Vr*?kcW|39F=$-fj<ce&m9;%UxRy-v)c>B-'
    '0#O*!8O30Gh(OhRJ7%)s+_TIxYSVICIh5zl9I42oEZaE&n<i@uC;qXI<{C})usOXG2s7Aatx9=swNKi8s}xmuC-S7C&>@tkRVQdS'
    'Cm0oZIXMM0OwN=Q54<GdX*&XHQ<UJjI*&G70R;H$08~wyibvfo-#P$9HJ-1zqz=73$EE7?Xgf7Jq`i0c*Yi(T3(5>I@BPQKuRovT'
    '%K_EQi*8{PL7>(VknQ0BwFK+<s%8wLBmw(h!0{=M@>Z_Ygn=~YXobxy#7`7aD)h&2%I;}ZH04Xtf*|1&rU_wu83%UM?_vjmz>HT3'
    'N5J^bQU(VqZNX-HXQJi*%vJ|OlUJe0Rm7<deP(ax3JlqNbj=80;guUPgjb0K?WNkqpe{BUJ?tX=0Dlk1CL`q5WO!Z!)ZOWh4Oie6'
    'f^|{c^@v4z!VYTJ+&G4l0ADUalome9Oziz0ag4zTA+yoZ*xcRjh?mux{%ot$<1Cdp%%pm~j$n!$-f)|VH|h=Ip%>_x0dA*oNR`RI'
    't^_!;A#!n?esDplxNT%sxHkuK31toGez6*sJcSj3WvHgdwJ|B;W&_gLnK#OJ<GQ%xxy2gt)NSL~!`qH29?Nib;8kvcIrt<}9`9m#'
    'kU`f82HNwF5@5jnzQM$Ge>wknezrIdKYhMBUp%G4CC@nQ`ZOzU4K56542vi>JvDsmNyrm+3lCqFKo2|Bc>*&H2JWpZcpiZYINVGh'
    'o_jfjacYpS9pknXm`m0Ua%@~q{~QYs$~(e2ozuNSo9=Ei+E%tm**&X48yBldnk%b;jD_`Xl*4MY<iIpq?#h|d7Ji#Lsnu4Cy~$Ry'
    'E5=rb>uqe*j+1j{=<oAzx86njxU8cX2mw?eVD?j=P-Eb)0KA+GcDqqd)aAffNM{4lu>p3(NzDspK}!<A6}gC`EJSlPzQ>HwOvPcY'
    '_$V9*79`DPTS;IDW^>f%kV0pbP6P_^I&c1NLLwYuE@Uq67XHBSsL)1u>*(Dd{}jqBD)MzEkMo05s|%|@4kB<rSo24DO*q!tafA21'
    'p}L?ON`&j(QWqfYm0;-P$W5+6CK&7_`9vqQkEY!_XnmbB4uLIn>pUOKPV2n1Z{<D0O|+F$4JETCY>6m$%O6)HN%W#pu6nYSiagb;'
    '%IKN}N~GQF?MqU1hzM3lXF_*QBb8BHHy~eftU0fm#VuQeD_h>Jad^bBNO-|vr*{-}k_LoRUEShY6PJ3J>CEPQZ_Ra>v`41--XiJX'
    'Ia63ct30#Y$7Xv~4#!NMiyV;Mr%u}c_EHJi6HB$`be2jDN7twf35sR^kY**Kr7Y;|uY+yhquW#bT9AHwvyOSt+?@0W!g@c`a=n=)'
    'oqaeIW&k0X?)S=(SFpJT4M}Yu6qgA=q#^^o(mgLEXK*3M9QM#+N`5c+!vY)^4mG#RakRxt{=^#?gS+(;atTJ@^AL!d5+T&13w5wA'
    'fgHyb<1Ie!wYtt9cjdq}Jlevg6uV0R)x298GFFVeB1N1rahn$<U!v1^T-i6bTF}F7w9ASJPwjg<6j<|3^eZnb^zab-ICTM*gVrnr'
    '7+2~%X>CE^plj%g%<}C3VP1Mr%GQ73DZyE$zXOU|C+DM*ptkd1(W^KJFzU$;Qe+uHe<_Nwv`07;&HLC5Ak|I=7@=2V-}ig8QL)cQ'
    '9;N3k324X^8Geu4Lua2bWCqV0syd^2FTm(+so$p7WpeDu&M&>TNtuTg86Vp~93w-bG?g6^{Pz(jFBkx+<;X3c*;RtssB<fbH{ePW'
    '$cC)^?oFsnD_I8+S#M>ZLWVC#Euvm(aBuiJx)((mW$ytU?0$Wb;GQp6ljp6oT87&^G%yhr>5bG<P?kCZWlYX0?-^6BW-v`d*wODG'
    'S}M$;+cM;2KL_adk9Nc|IQr9FszgvVTP!>BzT4)jR4$%4u4E=;n2Z0eb=PLJZCV|-;;mTxhnvsuvx&B#zr-+F@+PgBji6@&q3;6-'
    'k#v)r@u{oUj^=}ysofwMG-)s?hC`?qQoQULdfWZ`rqqJ#Mr>UY3OJNM%>~D>6U?(V-4?N7b8bVt#F7upYau#jzMrN;g)}52A&N7Z'
    'ZX-Xhm{TCgem!LuZKdi@S_LeDvz}9L%D!0V%Im$6^}}@!P?w<6c@tr+aG?kOUKJ``>q@9Dz!m5Wc2jv&ztgG(ZqI*j-t29+et7ey'
    'GmHdO)%#vc2Xx&Ib0nuf7R?`q*bSl>)9CO`u-#qzgu#)8*J?vvua>V{)qA~ik=mU0UcF)}u4XFKIRf~th5IHU**B+qI-TPGnQmS6'
    '1tj2)wc|!pz<Rw`(bVA@Fz+d(Isk4v-o<k+&M3Mmylw>Mq=}xIdFd*0x8@7DqCI%GtNVVnhGS>1dK8Td7BIV2@Ra3HddT8+l;2|U'
    'Kq+ffnT{TU?iA<!GIVLqFf55mtUUrkvmGmPc{aeAO?+mezX=_SsS@2Aj#cf#bS<cuD6%WluZ;(|W>zo~u#Z$`Ux6Eh6~)~ts6bbw'
    'SV4?s?MRB{<+02i3xq1RX+YrRhT%#oT^dz6UjtM?Xby|+&XSY`;i15Su4rf(!4vzq8W0<86fwIdYf2q~I${sicMZG~8XT{Jp7rAB'
    'iJM984=^^n@2x3$@2<i2Ke~|mzwG?ier+;La3lj>`Kb$2S7j%9ktZ_$X|`e87diVY1we(F+3t#@j{nlA{P~P^3Po*tRj##1E!{4%'
    'y;nVx&~YPNJ9Bn$@S%l8oF<KE3~VdOu5Im-3gLg<R8K|T2Ujtc$IALw0})79UWcP0mCkOb(8+Mv@r{T>S$c-nz|<<!YVF*(DY(#A'
    'SpX1h?h;Xs<%>+XPrxu?nz^`>`FB;*k?}C$QgRCV1^_>{KowM_5Bkdvz*yn)cngv&9_OhS?AvRy1K23Ar{&xtL5FDyA68@F0nDAi'
    '@0aP(*F;4XqzTnR_9*loZagYm1yh=2owTTIQ#E_Nq^kunRFa32R=YeNYZ$cCg)Kh-q3pg{$Ap<o=TM1E3m6dpK^|wF+H2k4<RDyk'
    '?d?TKUoo`T7xFK}z@-)jU5PexD^%qr#ZXlYC4Xn8)y-JYhJzZ}pTqRB7KRFTLL&x~7NQD~dEKSb{5m6%>S8~YiT3=bvl=qvuB&b6'
    '3Pc(YzkgMLIdjdOB~rP1f{=l%xi%^~N8Z-_Nvk#AyXMQC%0GaR4j@&e4Wp2q{$QS6SqUOq$p#fShxn}selT)Bbla;x@(MlyQPnnz'
    'TPp#LSfJJdoRzn9KYB?$W36mp?B`*a6mb|@CD<k2SL4hyWb93+=nJQK0R=Vyv$%69oj_*PWHr47@k289pT(lws~Ow>nClrFsWsU9'
    '+xgkg-thq=>pKZ4)>9B`%R`#Qv`zM+#$Eu7qEc)hl))?T&^WE|yVAE_+n`U8)B98BF8Ih2NatY@5q&;42QO8WJgmWBd;RM6GU&*G'
    'HXZmi>5yQkuQSxw1SBRRSJ%dfgtW`SNM$#>D!}LE>8vfWS9gw5jL0g=hCp3|Dy_84g@QCKc6o$pMcWbG0FI`1?1zKN%zt8ajQY-`'
    'RowZp%ixJwfC}hzL+Tn9Y^2>8FeMZK9I@8MPWK9Gr9JMO3g9`YY=s{vi~JarEabp~;MDv1%f*K)h_BSB1AZ@scXzmRvY6BFSL8}T'
    'Ivoum{Bphky#q&cwpf_Ycg+We@_X35S><qPE_*u~bwjq}E`~mvazdY;x0!Uzx?Pp~GRg_@G0I!2?Qdt?OV$bdyigD3qniF_G+lB&'
    'oLzhzAP4pghCR7oil%p<+8{C^g-u~d>Ao;TMGr$ye}{&5!iycoY50}#n9Kl}-Tw!P#aQP'
)


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _load_source() -> dict[str, object]:
    source = zlib.decompress(base64.b85decode(SOURCE_B85))
    actual = _blob_sha(source)
    if actual != SOURCE_BLOB:
        raise RuntimeError(f"embedded inventory source mismatch: expected {SOURCE_BLOB}, got {actual}")
    namespace: dict[str, object] = {"__name__": "orche_frozen_inventory_source", "__file__": SOURCE_PATH}
    exec(compile(source, SOURCE_PATH, "exec"), namespace)
    return namespace


def main() -> int:
    try:
        namespace = _load_source()
        original = namespace["build_outputs"]
        canonical = namespace["_canonical_json"]
        if not callable(original) or not callable(canonical):
            raise RuntimeError("reviewed inventory source has an invalid API")

        def frozen_build_outputs(repo_root: Path, repository: str, requested_ref: str) -> dict[str, bytes]:
            outputs = original(repo_root, repository, requested_ref)
            manifest = json.loads(outputs["baseline-manifest.json"])
            self_bytes = Path(__file__).read_bytes()
            manifest["generator"] = {
                "command": f"python {FROZEN_PATH}",
                "deterministic": True,
                "gitBlobSha": _blob_sha(self_bytes),
                "materialization": MATERIALIZATION,
                "path": FROZEN_PATH,
                "runtimeMutation": False,
                "sourcePath": SOURCE_PATH,
            }
            outputs["baseline-manifest.json"] = canonical(manifest).encode("utf-8")
            return outputs

        namespace["build_outputs"] = frozen_build_outputs
        entrypoint = namespace["main"]
        if not callable(entrypoint):
            raise RuntimeError("reviewed inventory source has no main entrypoint")
        return int(entrypoint())
    except (OSError, RuntimeError, ValueError, zlib.error) as exc:
        print(f"RESULT: FAIL baseline-inventory: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
