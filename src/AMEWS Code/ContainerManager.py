import os
import re
import glob
import random
import json
import time
import string
import keyboard
import subprocess
import pandas as pd
from datetime import datetime, timedelta
import cv2
from pyzbar.pyzbar import decode

from CustomTracker import CustomTracker
from CustomAlert import CustomAlert


class CustomBarcode:
    def __init__(self):
        self.cam = None  # camera object
        self.image = None  # image

    def finish(self):
        self.cam.release()
        cv2.destroyAllWindows()

    def check_camera(self, camera=0):  # check there is a camera
        self.cam = cv2.VideoCapture(camera)
        if self.cam.isOpened():
            name = self.cam.get(cv2.CAP_PROP_FOURCC)
            width = self.cam.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = self.cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fps = self.cam.get(cv2.CAP_PROP_FPS)
            print(
                "\n>> Camera%d : %s, %d x %d, %d frames/s"
                % (camera, name, width, height, fps)
            )
            return True
        else:
            return False

    def snapshot(self, camera=0, focus=100):  # take snapshot
        flag = 0
        self.image = None
        if self.check_camera(camera):
            focus = 5 * round(focus / 5)
            self.cam.set(
                cv2.CAP_PROP_FOCUS, focus
            )  # change focus, must be a multiple of 5
            time.sleep(1)

            print(">> Cleaning buffer, changed camera focus to %d" % focus)
            for i in range(5):  # repeated to clean camera buffer
                result, self.image = self.cam.read()
                # print(i+1,result)
                time.sleep(1)

            if not result:
                print(">> No image taken")
            else:
                flag = 1
        else:
            print(">> Camera %d not opened" % camera)
        self.cam.release()
        return flag

    def read_jpg(self, opt=0):
        self.image = cv2.imread("last_image.jpg")
        if opt:
            cv2.imshow("last image", self.image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    def read_barcode(self):  # read barcode
        if self.image.size:
            gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            barcodes = decode(gray)
            if barcodes:
                s = barcodes[0].data.decode("utf-8")
                print("\n>> Detected barcode %s\n" % s)
                return s
            else:
                return "0000XX"

    def snap_barcode(self, camera=0, focus=100):
        if self.snapshot(camera, focus):
            return self.read_barcode()
        else:
            return ""


class CustomDispatch:
    def __init__(self, keep=True):
        self.verbose = 1
        self.activate = False  # activate dispatching
        self.user = os.getlogin()
        self.dir = r"Z:\CONTAINERS"
        self.TRASH = os.path.join(self.dir, "TRASH")
        if not os.path.exists(self.TRASH):
            os.makedirs(self.TRASH)

        self.container = {}  # json object for container
        self.tracker = CustomTracker()

        if self.activate:
            self.load_UR5_status(keep)  # UR5 status with protocols

        # alphanumerical datetime coder
        self.ALPHABET = string.digits + string.ascii_uppercase  # alphanumericals
        self.BASE = len(self.ALPHABET)
        self.BASE_DATETIME = datetime(datetime.now().year, 1, 1)
        self.COUNT = 0

        # general status
        self.supplies = 0
        self.trash = 0
        self.storage = 0
        self.smtp = CustomAlert()
        self.smtp.instrument = "Dispatcher-AARL200@anl.gov"

        if self.activate:
            self.purge_containers()  # remove all empty containers
            pd.set_option("display.max_columns", None)

    ################################ container encoding date time => four alphanumerical symbols ############################

    def encode(self, n):
        if n == 0:
            return self.ALPHABET[0]
        result = []
        m = n
        while n:
            result.append(self.ALPHABET[n % self.BASE])
            n //= self.BASE
        s = "".join(reversed(result))
        s += self.ALPHABET[self.COUNT % self.BASE]
        if self.verbose == 2:
            print(
                "\n--- encoding container: COUNT=%d, BASE=%d" % (self.COUNT, self.BASE)
            )
            print(
                "--- %d seconds since the beginning of the year => code = %s\n" % (m, s)
            )
        self.COUNT += 1
        return s

    def decode(self, s):
        result = 0
        for char in s[:-1]:
            result = result * self.BASE + self.ALPHABET.index(char)
        return result

    def datetime2abcd(
        self, dt
    ):  # minutes since the beginning of a year to 4 alphanumeric symbols + count module alphabet length
        d = dt - self.BASE_DATETIME
        tm = int(d.total_seconds() // 60)
        return self.encode(tm).zfill(5)

    def abcd2datetime(self, code):  # decoding
        return self.BASE_DATETIME + timedelta(minutes=self.decode(code))

    #############################  container management ####################################

    def update(self, c):  # write container file
        code = c["code"]
        u = os.path.join(self.dir, "Container_%s.json" % code)  # network copy
        try:
            with open(u, "w") as f:
                json.dump(c, f, indent=4)
        except Exception as e:
            print(">> Error %s: cannot save container %s" % (e, code))

    def load(self, code):  # read container file
        s = os.path.join(self.dir, "Container_%s.json" % code)
        with open(s, "r") as f:
            self.container = json.load(f)
            return self.container
        return None

    def remove(self, code):  # delete container file
        f = os.path.join(self.dir, "Container_%s.json" % code)
        try:
            os.remove(f)
        except Exception as e:
            print(">> Error %s removing container file %s" % (e, code))

    def info(self, c):  # basic information about the container
        code = c["code"]
        if c["rack"]["instrument"] == "Trash":
            return code, "Trash", -1
        step = c["route"]["step"]
        r = c["route"]["route"]
        if step >= len(r):
            step = len(r) - 1
        instrument = r[step]
        return code, instrument, step

    def save(
        self, container=None, stamp=True
    ):  # timestamps, codes, and saves container object, json format - creation of the object
        if container is None:
            container = self.container
        if stamp:
            dt = datetime.now()
            container["creator"]["datetime"] = str(dt)
        print(
            ">> Saved %s container %s on %s"
            % (container["route"]["type"], container["code"], dt)
        )
        self.update(container)

    ########################### container queueing #######################################################################

    def service_request(
        self, code
    ):  # requestuing service by activation of "ready" code word
        c = self.load_container(code)
        if c:
            c["route"]["ready"] = "yes"
            self.update(c)

    def poll_containers(self):  # poll all containers in containers folder
        fs = glob.glob(os.path.join(self.dir, "Container_*.json"))
        for s in fs:
            if os.path.getsize(s):
                with open(s, "r") as f:
                    c = json.load(f)  # Load container
                    if c:
                        match = re.search(r"Container_(.*?)\.json$", s)
                        if (
                            match
                        ):  # make sure that the code corresponds to the file name
                            code = match.group(1)
                            if c["code"] != code:
                                c["code"] = code
                                self.update(c)
                        self.process_container(c)

    def purge_containers(self):  # poll all containers in containers folder
        fs = glob.glob(os.path.join(self.dir, "Container_*.json"))
        n = 0
        if len(fs):
            for s in fs:
                if os.path.getsize(s) == 0:
                    self.force_remove(s)
                    n += 1
        if n:
            print(">> Purged %d empty containers" % len(fs))

    def force_remove(self, s):  # force delete <s>
        if os.path.exists(s):
            with open(s, "w"):
                pass
            time.sleep(1)
            try:
                subprocess.run(["del", "/f", "/q", s], check=True, shell=True)
            except subprocess.CalledProcessError as e:
                print(">> Error %s (forced file removal)" % e)

    def process_container(self, c):  # process container
        if c["route"]["ready"] == "yes":
            code, instrument, step = self.info(c)

            print(
                "--- Classifier: container %s -> current instrument %s"
                % (code, instrument)
            )

            if instrument == "Trash":
                self.trash_container(c)
                return

            if instrument == "UR5":
                self.update_UR5(c)

            if instrument != "Storage":
                q = self.queue[instrument]
                if self.notinqueue(q, code):  # check instrument queue
                    record = {}
                    record["code"] = code
                    record["requested"] = str(datetime.now())
                    record["priority"] = "high"
                    q["queue"].append(record)
                    c["route"]["ready"] = "no"
                    self.update_queue(instrument)
            else:
                self.index(c)
            self.update(c)

    def notinqueue(
        self, q, code
    ):  # checks that container <code> is in the instrument queue <q>
        try:
            for record in q["queue"]:
                if "code" in record and record["code"] == code:
                    return False
        except Exception:
            print("Error %s: cannot access the queue, skip")
            return True
        return True

    def update_queue(self, instrument):  # update instrument queue
        u = os.path.join(self.dir, "Queue_%s.json" % instrument)  # network hard copy
        with open(u, "w") as f:
            json.dump(self.queue[instrument], f, indent=4)

    def load_queue(self, instrument, keep=True):  # load instrument queue
        u = os.path.join(self.dir, "Queue_%s.json" % instrument)  # network hard copy

        if not keep:
            self.queue[instrument] = {"queue": []}
            print(">> New queue for instrument %s" % instrument)
            return

        if not os.path.exists(u):
            self.queue[instrument] = {"queue": []}
            print(">> Queue file for instrument %s not found, nulled" % instrument)
            print("file path = %s" % u)
            return

        if os.path.getsize(u) == 0:
            self.queue[instrument] = {"queue": []}
            print(">> No containers queued for instrument %s found" % instrument)
            return

        try:
            with open(u, "r") as f:
                q = json.load(f)
                self.queue[instrument] = q
        except Exception as e:
            print(
                ">> Error %s: cannot load queue for instrument %s, skip"
                % (e, instrument)
            )
            self.queue[instrument] = {"queue": []}

        return self.queue[instrument]

    def remove_task(
        self, instrument, task=None, index=True
    ):  # remove task from queue, optionally index step, if task is None, remove the first task
        t = 0
        if instrument not in self.queue:
            return
        q = self.queue[instrument]["queue"]
        if len(q) == 0:
            return
        if task:
            t = q.index(task)
        code = q[t]["code"]
        del q[t]

        if self.verbose:
            print(
                ">> Removed task %d (container %s) from instrument %s queue"
                % (t, code, instrument)
            )

        c = self.load(code)
        c["route"]["ready"] = "yes"
        if index:
            self.index(c)

        self.update(c)
        self.update_queue(instrument)

    def index(self, c):  # index step
        dt = datetime.now()
        c["route"]["step"] += 1
        c["route"]["datetimes"].append(str(dt))

    def trash_container(
        self, c
    ):  # move container to trash folder and create waste bill
        dt = datetime.now()
        code = c["code"]
        s = "Container_%s.json" % code
        position = c["rack"]["position"]
        old = os.path.join(self.dir, s)
        new = os.path.join(self.TRASH, s)
        c["route"]["datetimes"].append(str(dt))

        if os.path.exists(old):
            print("\n>> Moves container %s to trash and creates waste bill\n" % code)

            try:
                # if not os.path.exists(new):
                with open(new, "w") as f:
                    json.dump(c, f, indent=4)

                waste = self.tracker.waste_bill(c["creator"]["content"])

                waste.to_csv(
                    os.path.join(self.TRASH, "waste_%s_%s.csv" % (code, position)),
                    index=True,
                )
            except Exception as e:
                print(">> Error %s (waste record)" % e)

            self.force_remove(old)

    ############################### UR5 status handling #####################################################################
    #
    #
    def FIFO_UR5(self):  # FIFO service in UR5 queue
        self.UR5_general_check()
        task, c = self.check_queue("UR5")
        if c:
            code = c["code"]
            if self.verbose:
                print(
                    "\n>> Processing container %s in UR5 queue, priority = %s"
                    % (code, task["priority"])
                )
            i_pick, f_pick = self.pick_UR5_check(c)
            i_drop, row, f_drop = self.drop_UR5_check(c)

            if f_pick == 1 or f_drop == 3:
                task["priority"] = "low"
                self.update_queue("UR5")
                return 3

            if self.pick_UR5(c, i_pick, f_pick):
                print(">> UR5 is stack picking container %s, abort" % code)
                self.smtp.alert(
                    ">> UR5 is stack picking container %s, abort" % code,
                    importance="High",
                )
                return 4  # termination

            if self.drop_UR5(c, row):
                print(">> UR5 is stack picking container %s, abort" % code)
                self.smtp.alert(
                    ">> UR5 is stack dropping container %s, abort" % code,
                    importance="High",
                )
                return 4  # termination

            self.UR5.loc[i_pick, "status"] = ""
            self.UR5.loc[i_pick, "stamp"] = ""
            self.update_UR5_line(c, i_drop)
            c["route"]["ready"] = "yes"
            self.update(c)

            if f_drop < 2:  # in place or storage
                self.remove_task("UR5", task, index=1 - f_drop)
                return 0
            else:  # in trash
                task["priority"] = "low"
                self.update_queue("UR5")
                print(">> Set low priority for container %s" % code)
                return 2

    def check_queue(self, instrument):
        q = self.load_queue(instrument, True)
        if q:
            q = q["queue"]
            if len(q) == 0:
                return None, None
            flag = 1
            for task in q:
                if task["priority"] == "high":  # high priority tasks are selected FIFO
                    flag = 0
                    break
            if flag:
                task = random.choice(q)  # low priority tasks are selected at random
            try:
                if task:
                    return task, self.load(task["code"])
            except:
                return None, None
        return None, None

    def update_UR5(self, c):  # update UR5 status file
        rack, _, instrument, position = self.UR5_info(c)
        for i, row in self.UR5.iterrows():
            if (
                instrument == row["instrument"]
                and rack in row["types"]
                and position == row["position"]
            ):
                self.update_UR5_line(c, i)
                return

    def update_UR5_line(self, c, i):  # updates UR5 status file line <i>
        rack, service, instrument, position = self.UR5_info(c)
        code = c["code"]
        dt = datetime.now()
        if self.verbose:
            print(
                ">> Updating UR5_status for rack=%s, instrument=%s, position=%s"
                % (rack, instrument, position)
            )
        self.UR5.loc[i, "status"] = "%s-%s" % (code, service)
        self.UR5.loc[i, "stamp"] = str(dt)
        self.write_UR5_protocol()

    def load_UR5_status(self, keep):  # load UR5 protocols
        f = os.path.join(self.dir, "UR5_status.csv")
        try:
            self.UR5 = pd.read_csv(f)
            self.UR5.fillna("", inplace=True)

            if not keep:
                self.UR5["comment"] = ""
                self.UR5["stamp"] = ""
                self.UR5["status"] = self.UR5["status"].apply(
                    lambda x: "" if x != "supply" else x
                )

            self.queue = {}
            s = "UR5"
            self.load_queue("UR5", keep)

            for _, row in self.UR5.iterrows():
                instrument = row["instrument"]
                if instrument not in self.queue:
                    s += " " + instrument
                    self.load_queue(instrument, keep)
            print(">> Creates UR5 queue for instruments: %s" % s)
            return 0
        except Exception as e:
            print(">> Error %s: cannot read UR5 status file %s" % (e, f))
            return 1

    def write_UR5_protocol(self):  # load UR5 protocols
        s = os.path.join(self.dir, "UR5_status.csv")
        try:
            self.UR5.to_csv(s, index=False)
            return 0
        except Exception:
            print(">> Error %s: cannot access UR5_status.csv")
            return 1

    def UR5_info(self, c, opt="pick"):  # opt=0 pick, opt=1 drop
        rack = c["rack"]["type"]
        service = c["route"]["type"]

        if opt == "drop":
            step = c["route"]["step"]
            instrument = c["route"]["route"][step + 1]
            position = None

        if opt == "pick":
            instrument = c["rack"]["instrument"]
            position = c["rack"]["position"]

        return rack, service, instrument, position

    def pick_UR5(self, c, i, flag):
        if flag == 1:
            self.UR5.loc[i, "status"] = ""
        protocol = "pick_%s_%s" % (
            self.UR5.loc[i, "instrument"],
            self.UR5.loc[i, "suffix"],
        )
        return self.UR5_action(protocol)

    def pick_UR5_check(self, c):
        rack, service, instrument, position = self.UR5_info(c, "pick")

        if self.verbose:
            print(
                "\n>> Check pick: rack=%s, service=%s, instrument=%s, position=%s"
                % (rack, service, instrument, position)
            )

        if service == "trash":
            return -1, 1
        for i, row in self.UR5.iterrows():
            if rack in row["types"] and instrument == row["instrument"]:
                if service == "supply":
                    if "Storage" == instrument and row["supply"] == "":
                        self.supplies = 0
                        return i, 0
                else:
                    if row["position"] == position:
                        return i, 0

        if service == "supplies":
            print(">> Run out of %s supplies, sent alert" % rack)
            if self.supplies == 0:
                self.supplies = 1
                self.smtp.alert("ran out of %s supplies" % rack, importance="High")
        else:
            print(
                ">> Cannot find UR5 protocol for instrument %s, picking rack %s"
                % (instrument, rack)
            )
            self.smtp.alert("cannot pick rack %s at instrument %s" % (instrument, rack))

        return -1, 1

    def drop_UR5(self, c, row):
        c["rack"]["position"] = row["position"]
        c["rack"]["instrument"] = row["instrument"]
        protocol = "drop_%s_%s" % (row["instrument"], row["suffix"])
        return self.UR5_action(protocol)

    def drop_UR5_check(self, c):
        rack, service, instrument, position = self.UR5_info(c, "drop")

        if self.verbose:
            print(
                ">> Check drop: rack=%s, service=%s, instrument=%s"
                % (rack, service, instrument)
            )

        df = self.UR5
        d = df[df["types"].str.contains(rack) & (df["status"] == "")]

        flag = 1
        for i, row in d.iterrows():
            if row["instrument"] == instrument:
                flag = 0
                return i, row, 0

        if (
            flag and instrument != "Storage"
        ):  # requested instrument is busy, place in storage
            if self.verbose:
                print("--- checks storage")
            flag = 0
            for i, row in d.iterrows():
                if row["instrument"] == "Storage":
                    flag = 0
                    print(
                        ">> Instrument %s unavailable, placed rack %s in storage"
                        % (instrument, rack)
                    )
                    return i, row, 1

        if flag and c["route"]["priority"] == "clear":  # storage is full
            # place in trash if priority is clear, do noting otherwise

            if self.verbose:
                print("--- checks trash")
            for i, row in d.iterrows():
                if row["instrument"] == "Trash":
                    print(">> Expected placement unavailable, trashing")
                    self.smtp.alert(
                        "Instrument & storage unavailable: forced removal of rack %s"
                        % (instrument)
                    )
                    self.UR5.loc[i, "comment"] = "forced removal"
                    return i, row, 2

        print(">> Cannot place, store or trash  rack %s" % rack)
        return -1, None, 3

    def UR5_general_check(self):
        self.UR5 = self.UR5.fillna("")
        self.supplies_check()
        self.storage_check()
        self.trash_check()

    def supplies_check(self):
        df = self.UR5.copy()
        count = df[
            df["status"].str.contains("supply", case=False)
            & df["instrument"].str.contains("Storage", case=False)
        ].shape[0]

        del df

        if self.verbose:
            print(" --- %d supply items remain" % count)

        if count == 0 and self.supplies == 0:
            self.supplies = 1
            print(
                "\n****************  ALERT: ran out of supplies ****************",
                importance="High",
            )
            self.smtp.alert("run out of supplies")
        else:
            self.supplies = 0

        if count:
            return 0
        else:
            return 1

    def trash_check(self):
        df = self.UR5.copy()
        df = df[
            (df["status"] == "") & (df["instrument"].str.contains("Trash", case=False))
        ]
        count = df.shape[0]

        del df

        if self.verbose:
            print("--- %d empty trash slots remains" % count)

        if count == 0 and self.trash == 0:
            self.trash = 1
            print("\n****************  ALERT: ran out of trash slots ****************")
            self.smtp.alert("ran out of trash slots", importance="High")
        else:
            self.trash = 0

        return count

    def storage_check(self):
        df = self.UR5.copy()
        df = df[
            (df["status"] == "")
            & (df["instrument"].str.contains("Storage", case=False))
        ]
        count = df.shape[0]

        del df

        if self.verbose:
            print("--- %d empty storage slots" % count)

        if count == 0 and self.storage == 0:
            self.storage = 1
            print(
                "\n****************  ALERT: ran out of empty storage slots ****************"
            )
            self.smtp.alert("ran out of storage slots", Importance="High")
        else:
            self.storage = 0

        return count

    def UR5_action(self, protocol):  # execute UR5 protocol; fake action
        if self.verbose:
            print(">> UR5 called protocol %s" % protocol)
        time.sleep(1)
        return 0

    def BK_action(self):  # BK fake action
        task, _ = self.check_queue("BK")
        if task:
            if self.verbose:
                print(">> BK action")
            time.sleep(1)
            self.remove_task("BK")
        return 0

    def ICP_action(self):  # ICP fake action
        task, _ = self.check_queue("ICP")
        if task:
            if self.verbose:
                print(">> ICP action")
            time.sleep(1)
            self.remove_task("ICP")
        return 0

    ################################################ manager ################################################################

    def manager(self):
        while 1:
            if keyboard.is_pressed("ctrl+q"):  # Check if Ctrl+Q is pressed
                print(">> Ctrl-Q pressed, breaking the polling loop")
                break
            self.poll_containers()
            if self.UR5_tasks() == 3:
                break
            time.sleep(30)


##########################################################################################################################


def test():
    m = CustomDispatch(keep=False)
    for i in range(20):
        m.poll_containers()
        if m.FIFO_UR5() == 4:
            break
        m.ICP_action()
    m.purge_containers()


if __name__ == "__main__":
    test()
