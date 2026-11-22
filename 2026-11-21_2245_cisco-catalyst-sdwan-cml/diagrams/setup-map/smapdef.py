"""Setup-scene side panel: which topology parts light up at which sentence,
and what the 9-step progress bar shows.  SM[sid] = [(sentence, [tags])]
PROG[sid] = ("use", [steps], caption)  file explained, used by those steps
          | ("run", n)                  live build, step n running"""
CT=["mgr","val","ctl"]; UL=["gw","vpn0","inet","mpls"]
SM={
 "302_yaml":[(0,["cml"]),(1,["cml"]+CT+["edge"]),(2,["serial"]),(6,["val","gw"])],
 "303_yaml":[(0,["you","mgmt","mgr"]),(1,UL),(2,CT),(4,["mgr"])],
 "304_yaml":[(0,["hosts"]),(2,["sites","edge"]),(3,["edge","inet","mpls","hosts"]),(4,["DC","DC-E1"]),(6,["DC-E1","inet","mpls"]),(7,["DC-E1"]),(8,["DC-SRV"])],
 "305_yaml":[(0,["BR1","BR1-E1","BR1-E2"]),(3,["BR1-PC","BR1-GUEST"]),(4,["BR2","BR2-E1","BR2-PC","BR2-GUEST","BR3","BR3-E1","BR3-PC"]),(5,["sites"])],
 "306_yaml":[(0,["tun","pol"]),(1,["inet","mpls"]),(2,["tun"]),(3,["pol"]),(6,["pol","DC"])],
 "310_cfg":[(0,[]),(1,["ca"]),(3,["you","mgmt"]),(7,[])],
 "311_cfg":[(0,[]),(1,UL),(2,["sites","hosts"]),(3,["edge","inet","mpls"]),(4,["hosts"]),(5,["sites","edge"])],
 "320_cml":[(0,["cml","you"])],
 "321_cml":[(0,["cml"]),(1,["edge"]),(2,["cml"]),(3,["edge"])],
 "322_cml":[(0,["cml"]),(1,["DC-E1","mpls"])],
 "330_mgr":[(0,["mgr","you","mgmt"])],
 "331_mgr":[(0,["mgr"])],
 "332_mgr":[(0,["mgr"]),(1,["val","ctl"]),(2,["ca"]+CT)],
 "333_mgr":[(0,["serial"]),(1,["edge"]),(2,["cg"])],
 "334_mgr":[(0,["cg"]),(2,["cg","edge"]),(6,["pol"]),(7,["mgr","tun"])],
 "340_pki":[(0,["ca"]),(1,["ca"]+CT),(3,["ca"])],
 "341_pki":[(0,["ca"]),(1,["ca"]+CT),(3,["ca"])],
 "350_render":[(0,["cml"]),(1,["edge"]),(3,CT),(4,["cml"])],
 "351_render":[(0,CT+["gw","vpn0"]),(2,CT)],
 "352_render":[(0,["cml"]),(1,["mgr"]),(2,["val"]),(5,["ctl"]),(6,UL+["mgmt"]),(7,["cml"])],
 "353_render":[(0,["hosts"]),(1,["sites"]),(2,["cml"])],
 "360_cg":[(0,["cg"]),(1,["cg","edge"])],
 "361_cg":[(0,["cg","edge"]),(2,["tun"]),(6,["inet","mpls","gw"]),(9,["val"])],
 "362_cg":[(0,["edge","inet","mpls"]),(3,["tun"]),(4,["inet"]),(6,["mpls"])],
 "363_cg":[(0,["edge","hosts"]),(2,["BR1","BR1-E1","BR1-E2"]),(4,["edge","hosts"])],
 "364_cg":[(0,["cg"])],
 "365_cg":[(0,["edge"]),(3,["edge","cg"])],
 "370_pol":[(0,["pol"])],
 "371_pol":[(0,["pol"]),(4,["hosts"])],
 "372_pol":[(0,["pol","v10"]),(2,["mpls","v10"]),(4,["v20","inet"])],
 "373_pol":[(0,["sites"]),(3,["ctl","v20"]),(4,["DC","v20"])],
 "374_pol":[(0,["v10","tun"]),(1,["pol","edge"])],
 "380_con":[(0,["cml","you"]),(3,["edge","hosts"])],
 "381_con":[(0,["cml","you"]),(3,["edge"]),(5,["hosts"])],
 "401_tpl":[(0,CT),(3,["mgr"]),(6,["mgr","ctl"]),(7,["val"]),(9,["ca"]+CT)],
 "402_tpl":[(0,CT),(4,["val"]),(6,CT)],
 "403_tpl":[(0,["vpn0","gw"]+CT),(6,["mgr","mgmt","you"])],
 "404_gw":[(0,["gw"]),(2,["gw","vpn0"]+CT),(3,["gw","inet","mpls"]),(4,UL),(6,["gw","inet","vpn0"])],
 "405_gw":[(0,["gw","val"]),(4,UL)],
 "406_gw":[(0,["gw"]),(3,["gw","inet","vpn0"]),(6,["mpls"])],
 "407_host":[(0,["hosts"])],
 "408_topo":[(0,["cml"])],
 "502_main":[(0,[])],
 "503_main":[(0,[])],
 "504_reset":[(0,["cml","ca"])],
 "505_list":[(0,[])],
 "510_s1":[(0,["ca"])],
 "511_s1":[(0,["ca"])],
 "520_s2":[(0,["cml"]),(6,["cml","sites","hosts"]+CT+UL)],
 "521_s2":[(0,["cml"]),(2,["sites","hosts"]+CT+UL),(3,["sites"])],
 "530_s3":[(0,["mgr","you","mgmt"]),(4,["mgr","val"]),(5,["mgr","ca"]),(8,["mgr"])],
 "531_s3":[(0,["mgr","you"])],
 "532_s3":[(0,["mgr"]),(7,["mgr","ca","val"])],
 "540_s4":[(0,CT),(4,["ca"]+CT)],
 "541_s4":[(0,["ctl"])],
 "542_s4":[(0,["val","ctl"]),(2,["ca"]+CT),(8,CT+["vpn0"])],
 "550_s5":[(0,["serial","mgr"]),(3,["serial","val"])],
 "551_s5":[(0,["serial"])],
 "560_s6":[(0,["cg"])],
 "561_s6":[(0,["cg"]),(2,["cg","inet","mpls"]),(3,["cg","hosts"]),(5,["cg"])],
 "570_s7":[(0,["edge"]),(1,["serial","edge"]),(3,["cg","edge"]),(6,["cg","mgr"])],
 "571_s7":[(0,["mgr","edge"]),(1,["cml","edge"]),(2,["edge","inet","mpls","hosts"]),(4,["edge"])],
 "572_bs":[(0,["BR1-E1"]),(2,["BR1-E1","val"]),(4,["BR1-E1","ca"])],
 "573_bs":[(0,["BR1-E1","cg"]),(2,["BR1-E1","tun"])],
 "574_bs":[(0,["BR1-E1","inet"]),(4,["BR1-E1","mpls"])],
 "575_bs":[(0,["BR1-E1","tun"]),(1,["BR1-E1","BR1-PC","BR1-GUEST"])],
 "576_bs":[(0,["BR1-E1","inet","mpls"]),(2,["BR1-E1","BR1-PC","BR1-GUEST"])],
 "577_bs":[(0,["BR1-E1","tun"])],
 "578_s7":[(0,["edge"]),(2,["cg","edge"]),(3,["cml","edge"])],
 "580_s8":[(0,["edge"]),(6,["edge","gw","val"]),(7,["val","serial"]),(8,["mgr","ctl","edge"]),(9,["tun","edge"])],
 "581_s8":[(0,["edge"]),(5,["edge","tun"]+CT)],
 "602_s9":[(0,["pol"]),(3,["ctl","v20"]),(7,["pol","edge"])],
 "603_pol":[(0,["pol"]),(3,["pol","v10","v20"])],
 "604_pol":[(0,["pol","v10"]),(4,["mpls","v10"]),(7,["tun"]),(9,["mpls"]),(10,["inet"]),(11,["tun"])],
 "608_s9":[(0,["edge"]),(3,["edge","ctl","mgr","inet","mpls"]),(4,["tun"]),(6,["BR1","BR1-E1","BR1-E2"]),(8,["DC","DC-E1","BR2","BR2-E1","BR3","BR3-E1"])],
 "609_s9":[(0,["pol"]),(4,["ctl","v20"]),(6,["pol","edge"]),(7,[])],
}
A=list(range(1,10))
PROG={}
def _u(ids,steps,cap):
    for i in ids: PROG[i]=("use",steps,cap)
_u(["302_yaml","303_yaml","304_yaml","305_yaml","306_yaml"],A,"lab.yaml is read by every step")
_u(["310_cfg","311_cfg"],A,"config.py is used by every step")
_u(["320_cml","321_cml","322_cml"],[2,7],"cml.py: steps 2 and 7, and failover tests")
_u(["330_mgr","331_mgr","332_mgr","333_mgr","334_mgr"],[3,4,5,6,7,8,9],"manager.py: steps 3 to 9")
_u(["340_pki","341_pki"],[1,3,4],"pki.py: steps 1, 3 and 4")
_u(["350_render","351_render","352_render","353_render"],[2],"render.py: step 2")
_u(["360_cg","361_cg","362_cg","363_cg","364_cg","365_cg"],[6,7],"configgroup.py: steps 6 and 7")
_u(["370_pol","371_pol","372_pol","373_pol","374_pol"],[9],"policy.py: step 9")
_u(["380_con","381_con"],[],"console.py: used by verify.py and demo.py")
_u(["401_tpl","402_tpl","403_tpl","404_gw","405_gw","406_gw","407_host","408_topo"],[2],"Day-zero templates: rendered in step 2")
_u(["502_main","503_main"],A,"build.py runs all nine steps")
for i,n in [("504_reset",0),("505_list",0),("510_s1",1),("511_s1",1),("520_s2",2),("521_s2",2),("530_s3",3),("531_s3",3),("532_s3",3),
            ("540_s4",4),("541_s4",4),("542_s4",4),("550_s5",5),("551_s5",5),("560_s6",6),("561_s6",6),("570_s7",7),("571_s7",7),
            ("572_bs",7),("573_bs",7),("574_bs",7),("575_bs",7),("576_bs",7),("577_bs",7),("578_s7",7),("580_s8",8),("581_s8",8),
            ("602_s9",9),("603_pol",9),("604_pol",9),("608_s9",8),("609_s9",9)]:
    PROG[i]=("run",n)
assert set(SM)==set(PROG), set(SM)^set(PROG)
