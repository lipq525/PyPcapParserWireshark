''' 
Authors: Francisco Viramontes, Seth Decker, Nestor Pereira, Mario Esparza

Description: This program is a packet parser intended to accomplish two
 things: take statistical information from all the users in one pcap file 
 in the working folder and organizes it between a set amount of conversations
 between two users and displays it in a list in the format of: 
     
 [Key(To upload to a database), Timestamp,  mac source, mac destination,
 ip source(if there is none, it will say "None"), 
 ip destination(if there is none, it will say "None"), 
 bits from source to destination, passive, 2GHz, ofdm, cck, gfsk,
 5GHz, gsm, cck_ofdm, number of packets in the conversation, 
 average signal strength, average data rate, duration in microseconds(us),
 preamble duration in microseconds(us),  physical type b, physical type g,
 physical type n, channel]. 
 
 Lastly, the parser will see if there are any packets that use the Domain Name 
 Service protocol (dns) and check the dns packets for answers. If the dns 
 packets have answers it will try to read them and put them into a dictionary
 so that they can use the list of unique IP addresses and see what websites 
 were visited to determine what services (Video, Audio, VoIP, etc) were used.

Input: Any pcap file that has packets that use 802.11 protocols, this parser 
 DOES NOT WORK with pcap files that captured packets via Ethernet connection.
 This parser has only worked with pcap files from wireshark so far.

Output: This parser has 2 intended outputs

 The statistical converation list(Displays two converations between four users)
 [[5, 1491498813, '2c:56:xx:xx:50:e1','ff:ff:ff:ff:ff:ff', '91.189.91.26',
 '10.81.198.43', 9880, 0, 5, 0, 5, 0, 0, 0, 0, 4, -102, 1, 0, 0, 'b'], 
 [128, 1491498813, '00:0b:xx:xx:59:c0','20:68:xx:xx:d4:74', '10.81.198.43', 
 '72.21.91.29', 9814768, 0, 873, 59, 0, 0, 0, 0, 814, 872, -36, 55, 0, 0, 'n']]

 DNS answer dictionary
 {'172.217.5.78':'www.youtube.com', '35.166.101.77': 'aus5.mozilla.org',
 '216.58.193.194':'securepubads.g.doubleclick.net',
 '208.77.78.221': 'www.google.com', '54.191.164.105': 'aus5.mozilla.org', 
 '54.68.139.233': 'services.addons.mozilla.org', 
 '52.11.31.31': 'incoming.telemetry.mozilla.org'}
'''

from glob import glob
import pyshark
import DatabaseConnect as dc
#import psycopg2
import time

##################################################################

# Take a look at keeping the program running (maybe a command prompt script??)

##################################################################
db = dc.DatabaseConnect()
db.connect()
'''
def getMACKey(v):
    for k in v:
        for j in v[k]:
            for m in v[k][j]:
                for n in v[k][j][m]:
                    if k == "ff:ff:ff:ff:ff:ff":
                        v[k][j][m][n][1] = '0'
                    if j == "ff:ff:ff:ff:ff:ff":
                        v[k][j][m][n][2] = '0'
    return v
def getIPKey(v):
    pass
'''
    
#This function checks specific channel flags of a packet
# also updates statDict
def check_flags(pkt, cflags):
    try:
        #Complementary Code Keying
        if pkt.channel_flags_cck != "0":
            cflags["cck"] += 1  
        #Orthogonal Frequency Division Multiplexing
        if pkt.channel_flags_ofdm != "0":
            cflags["ofdm"] += 1
        #Uses 2 GHz spectrum
        if pkt.channel_flags_2ghz != "0":
            cflags["twoghz"] += 1 
        #Uses 5 GHz spectrum
        if pkt.channel_flags_5ghz != "0":
            cflags["fiveghz"] += 1 
        #Passive mode is on
        if pkt.channel_flags_passive != "0":
            cflags["passive"] += 1 
        #Dynamic CCK-OFDM
        if pkt.channel_flags_dynamic != "0":
            cflags["cck_ofdm"] += 1 
        #Gaussian frequency shift keying
        if pkt.channel_flags_gfsk != "0":
            cflags["gfsk"] += 1 
        #GSM at 900 MHz
        if pkt.channel_flags_gsm != "0":
            cflags["gsm"] += 1 
        #Returns the updated dictionary
        return cflags
    except:
        pass

serverKey = 0 #db.getNextDataKey()
start_time = time.time()
#Looks for any pcap files in working directory
for file_name in sorted(glob("*.pcap")):
    #If there are any, it will open them as pcap_data
    with open(file_name, "rb") as pcap_data:
        
        #Loads .pcap data into variable "pktdata"
        pktdata = pyshark.FileCapture(pcap_data, keep_packets = False)
        #Empty list of Unique MAC addresses
        uniqueMAC = []                            
        #Interger counter for number of users based on unique MAC address
        numOfUsers= 0                               
        #Cumulitive Bits
        cumulBits = 0
        #List of dns answers for the pcap file (if there are any)
        dns_list = []
        #Gets dns answers (if any) and puts in a dictionary.
        # It has this format: {ip_addr : website that it belongs to}
        dns_addr = {}
        #Dns answers from mobile devices
        mdns_addr = {}                          
        #Dictionary that reads on organizes statistics from packets
        statDict = {}  
        #Cumulitive channel flag counter
        cflags = {"cck": 0,"ofdm": 0,"twoghz": 0,"fiveghz": 0,\
        "passive": 0,"cck_ofdm": 0,"gfsk": 0,"gsm": 0} 
        #Cumulative physical type counter
        ptype = {"b": 0,"g": 0,"n": 0}
        #This list gets everything ready to upload to a database
        listFinal = []
        
        n = 0
        for pkt in pktdata:
            #Needs to be documented
            if n == 0:
                pktfirst = pkt
            n += 1
            #Packet number
            if n % 1000 == 0:
                print "Packet: " + str(n)

            #Timestamp in UTC/Epoch time
            ##print pkt.sniff_timestamp
            
            #Channel Flag counter between two users
            cflags_c = {"cck": 0,"ofdm": 0,"twoghz": 0,"fiveghz": 0,\
            "passive": 0,"cck_ofdm": 0,"gfsk": 0,"gsm": 0} 
            
            #Physical type counter between two users
            ptype_c = {"b": 0,"g": 0,"n": 0}
            
            #Computing bits in packet n and adding to cumulitive bits
            try:
                #Amount of bits from the nth packet
                pktBits = int(pkt.length) * 8
                #Calculation of cumulitive bits
                cumulBits += pktBits
            except:
                pass
                
            #Taking a look at IPv4 information
            try:
                #Source IP address of the packet
                ip_src = str(pkt.ip.src)
                #Destination IP address of the packet
                ip_dst = str(pkt.ip.dst)
                
                #If we encounter DNS packets we want to see which domains a user
                # is looking for so we can see what services they may use.               
                try:
                    #Full Qualified Domain Name
                    fqdn = pkt.dns.qry_name
                    #Adding the fqdn to a list so we can  go through the unique
                    # IP addresses we find and replace it with the fqdn
                    if fqdn not in dns_list:
                        dns_list.append(fqdn)
                except:
                    pass
                
                try:
                    #DNS response packets can have multiple answers to a DNS
                    # query, they can range from 1 - 9 answers so here we are
                    # trying to pick up as much as we can.
                    dns_addr[pkt.dns.a] = fqdn
                    dns_addr[pkt.dns.a_0] = fqdn
                    dns_addr[pkt.dns.a_1] = fqdn
                    dns_addr[pkt.dns.a_2] = fqdn
                    dns_addr[pkt.dns.a_3] = fqdn
                    dns_addr[pkt.dns.a_4] = fqdn
                    dns_addr[pkt.dns.a_5] = fqdn
                    dns_addr[pkt.dns.a_6] = fqdn
                    dns_addr[pkt.dns.a_7] = fqdn
                    dns_addr[pkt.dns.a_8] = fqdn
                except:
                   pass
                try:
                    #Now we try DNS response packets for phones
                    mdns_addr[pkt.mdns.dns_a] = fqdn
                    mdns_addr[pkt.mdns.dns_a_0] = fqdn
                    mdns_addr[pkt.mdns.dns_a_1] = fqdn
                    mdns_addr[pkt.mdns.dns_a_2] = fqdn
                    mdns_addr[pkt.mdns.dns_a_3] = fqdn
                    mdns_addr[pkt.mdns.dns_a_4] = fqdn
                    mdns_addr[pkt.mdns.dns_a_5] = fqdn
                    mdns_addr[pkt.mdns.dns_a_6] = fqdn
                    mdns_addr[pkt.mdns.dns_a_7] = fqdn
                    mdns_addr[pkt.mdns.dns_a_8] = fqdn
                except:
                   pass
                
            except:
                ip_src = "None"
                ip_dst = "None"
                
            #Computing statistics from user A to user B
            try:         
                #Source MAC address
                mac_src = str(pkt.wlan.sa)
                #Destination MAC address
                mac_dst = str(pkt.wlan.da)
                #Integer version of time stamp
                ts = int(float(pkt.sniff_timestamp))
                
                #Dictionary that takes and updates statistics sent between two 
                # users. This is the Format: 
                # {key : [timestamp, MAC src, MAC dst, ip src, ip dst, 
                # bits from src to dst,  passive, 2GHz, ofdm, cck, gfsk,
                # 5GHz, gsm, cck_ofdm, number of packets in conversation,
                # cumulitive signal strength, cumulitive data rate,
                # duration (us), preamble duration (us),  physical type b,
                # physical type g, physical type n, channel]}
                
                if mac_src not in statDict:
                    statDict[mac_src] = {mac_dst : {ip_src : {ip_dst : [ts,\
                    mac_src, mac_dst, ip_src, ip_dst, pktBits, 0, 0, 0, 0,\
                    0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]}}} 
                #For multiple sources that have different destinations
                elif mac_dst not in statDict[mac_src]: 
                    statDict[mac_src].update({mac_dst : {ip_src : {ip_dst :\
                    [ts, mac_src, mac_dst, ip_src, ip_dst, pktBits, 0, 0,\
                    0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]}}})
                #If the source IP changes we want to record the conversation
                elif ip_src not in statDict[mac_src][mac_dst]:
                    statDict[mac_src][mac_dst].update({ip_src : {ip_dst :\
                    [ts, mac_src, mac_dst, ip_src, ip_dst, pktBits, 0, 0,\
                    0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]}})
                #If the desination IP changes we also want to record the convo
                elif ip_dst not in statDict[mac_src][mac_dst][ip_src]:
                    statDict[mac_src][mac_dst][ip_src].update({ip_dst :\
                    [ts, mac_src, mac_dst, ip_src, ip_dst, pktBits, 0, 0,\
                    0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]})
                #Updates already existing converations in dictionary
                else:
                    #Bits between user A and user B
                    statDict[mac_src][mac_dst][ip_src][ip_dst][5] += pktBits
                    #Number of packets between user A and user B
                    statDict[mac_src][mac_dst][ip_src][ip_dst][14] += 1
                    
#                getMACKey(statDict)
#                getIPKey(statDict)
                
                
                #Function calls for checking/updating channel flags   
                check_flags(pkt.radiotap,cflags)
                check_flags(pkt.radiotap,cflags_c)
                
                #This block updates channel flags betweens users in statDict
                iterator = 6
                for f in cflags:
                    if iterator < 14:
                        statDict[mac_src][mac_dst][ip_src][ip_dst]\
                        [iterator] += cflags_c[f]
                        iterator += 1
       
                #Looking at signal properties of the packet
                try:
                    #Determines the physical type, 802.11b/g/n
                    if pkt.wlan_radio.phy == "4":
                        #802.11b
                        ptype_c["b"] += 1
                    if pkt.wlan_radio.phy == "6":
                        #802.11g
                        ptype_c["g"] += 1
                    if pkt.wlan_radio.phy == "7":
                        #802.11n
                        ptype_c["n"] += 1
                        
                    #Updates physical type to the dictionary
                    try:
                        #Increases counter for physical type (802.11b)
                        statDict[mac_src][mac_dst][ip_src][ip_dst][19]\
                        += ptype_c["b"]
                    except:
                        pass
                    try:
                        #Increases counter for physical type (802.11g)
                        statDict[mac_src][mac_dst][ip_src][ip_dst][20]\
                        += ptype_c["g"]
                    except:
                        pass
                    try:
                        #Increases counter for physical type (802.11n)
                        statDict[mac_src][mac_dst][ip_src][ip_dst][21]\
                        += ptype_c["n"]
                    except:
                        pass
                    
                    #Signal strength in decibels
                    signal_strength = int(pkt.wlan_radio.signal_dbm)
                    #Adds to the signal strength part of the dictionary
                    statDict[mac_src][mac_dst][ip_src][ip_dst][15]\
                    += signal_strength
                    
                    #Data rate from source to destination in Mb/s
                    d_rate = int(pkt.wlan_radio.data_rate)
                    #Adds to the data rate part of the dictionary
                    statDict[mac_src][mac_dst][ip_src][ip_dst][16] += d_rate

                    #Gives what channel is being used
                    channel = int(pkt.wlan_radio.channel)
                    '''
                    try:
                        #Updates the channel type (1-11)
                        statDict[mac_src][mac_dst][ip_src][ip_dst][22]=channel
                    except:
                        pass
                        '''

                    #Duration in microseconds
                    dur = int(pkt.wlan_radio.duration)
                    #Adds duration of the packet to get cumulitive value (us)
                    statDict[mac_src][mac_dst][ip_src][ip_dst][17] += dur
                    
                    #Preamble duration in microseconds(us)
                    preamble = int(pkt.wlan_radio.preamble)
                    #Adds preamble duration of packet to get cumulitive 
                    # value (us)
                    statDict[mac_src][mac_dst][ip_src][ip_dst][18] += preamble
                    
                except:
                    pass
                
                #This adds all unique MAC addresses to a list and counts number 
                # of users based on number of unique MAC addresses
                if mac_src not in uniqueMAC:
                    uniqueMAC.append(mac_src)
                    numOfUsers += 1
                if mac_dst not in uniqueMAC:
                    uniqueMAC.append(mac_dst)
                    numOfUsers += 1 
            except:
                try:
                    #Work in progress to deal with a specific type of
                    # 802.11 packet
                    pkt.wlan.ra
                    
                except:
                    pass
        
        if n != 0:
            pktlast = pkt
                
            #Average for signal strength and data rate:
            try:
                for k in statDict:
                    for j in statDict[k]:
                        for m in statDict[k][j]:
                            for n in statDict[k][j][m]:
                                #Number of packets in converation/total signal strength
                                statDict[k][j][m][n][15] = \
                                statDict[k][j][m][n][15]/statDict[k][j][m][n][14]
                                #Number of packets in converation/total data rate
                                statDict[k][j][m][n][16] = \
                                statDict[k][j][m][n][16]/statDict[k][j][m][n][14]
            except:                
                pass
            
            #Puts statDict into a more readable list, ready to push to a database 
            #Format:
            # [key, timestamp, MAC src, MAC dst, ip src, ip dest, 
            # bits from src to dst, passive, 2GHz, ofdm, cck, gfsk,
            # 5GHz, gsm, cck_ofdm, # of pkt in convo, 
            # avg signal strength, avg data rate, cumulitive duration(us),
            # cumulitive preamble duration(us), physical type b,
            # physical type g, physical type n]
            for k in statDict: 
                for j in statDict[k]:
                    for m in statDict[k][j]:
                        for n in statDict[k][j][m]:
                            #The key is made by concatenating the timestamp with
                            # source and destination MAC addresses
                            l = serverKey
                            listFinal.append([l] + statDict[k][j][m][n])
                            serverKey += 1
                            
            #Finally, we print everything
            if numOfUsers > 0: 
                #The two intended outputs
                
                tableName = "Ze Table 3"
                db.writeDataTable(tableName)
                db.writeData(tableName, listFinal)
                #print db.readDataTable("cpp_yo")
                #print db.getTableNames()
                db.disconnect()
                
                for k in listFinal:
                    for d in dns_addr:
                        if k[4] == d:
                            k[4] = dns_addr[d]
                        if k[5] == d:
                            k[5] = dns_addr[d]
                print"\n"
#                for h in dns_addr:
#                    print h + " " + dns_addr[h]
#                for h in mdns_addr:
#                    print h + "_" + mdns_addr[h]
                print("--- %s seconds ---" % (time.time() - start_time))
            else:
                print "There are no users/data for this pcap file: " + str(file_name)