## 2026-10-22: Expanded VM root disk

Problem: / only 30G with 9.7G free. `sudo vgs` showed 30.47G unallocated (VFree).
Cause: the Ubuntu installer only allocated about half the volume group to ubuntu-lv.
Fix: `sudo lvextend -r -l +100%FREE /dev/ubuntu-vg/ubuntu-lv` (grows LV + ext4 online)
Verification: `df -h /` went from 30G size / 9.7G avail to 60G / 39G. VFree is now 0. Used unchanged at 19G.
