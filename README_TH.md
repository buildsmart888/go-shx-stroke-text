# GO SHX Stroke Text v0.2.0 — Extension for IngeTrazo

ปลั๊กอินแปลงเส้นตัวอักษรจาก **ไฟล์ `.shx`/`.shp` จริง** ด้วย `ezdxf.fonts.shapefile` ไม่ใช้ TTF Outline และไม่แปลงตัวอักษรเป็นฐานข้อมูลเอง

## ติดตั้ง (Windows / IngeTrazo ที่รองรับ Extension API v2)

1. แตกไฟล์ **GO_SHX_Stroke_Text_v0.2.0_Plugin.zip** ที่แจก: จะได้โฟลเดอร์ `go_shx_stroke_text` เพียงโฟลเดอร์เดียว
2. เปิด IngeTrazo → **Extensions → Open plugins folder**
3. คัดลอกโฟลเดอร์ `go_shx_stroke_text` ลงไปในโฟลเดอร์ Extensions/Plugins ที่โปรแกรมเปิดให้ (ปกติ `%APPDATA%\ingetrazo\plugins\`)
4. ปิดและเปิด IngeTrazo ใหม่ทั้งหมด แล้วไปที่ **Extensions → GO SHX Stroke Text → Open Stroke Text Builder…**
5. เลือก `.shx` ของคุณเอง ใส่ข้อความ และกด Preview → Create Model Text หรือ Create / Update Sheet Text

> หากโหลดแล้วแจ้ง `This IngeTrazo Python environment needs ezdxf >= 1.1`, ให้ตรวจ Python ที่ IngeTrazo ใช้จริง ไม่ใช่ลง ezdxf แค่ใน Python เครื่องอื่น. บางไฟล์ SHX ต้องมีสิทธิ์ใช้งานตามเจ้าของฟอนต์.

มีไฟล์ `install_windows.cmd` ใน **Source ZIP** สำหรับสำรองและคัดลอกลงโฟลเดอร์ปลั๊กอินแบบอัตโนมัติ.

## ฟีเจอร์

- อ่าน SHX/SHP ตรงจากไฟล์ ไม่ต้อง convert เป็น `data`, ไม่สลับไปใช้ Windows TTF อัตโนมัติ
- **Check all glyphs**: ตรวจตัวอักษรที่ขาด **ครบทั้งข้อความ** ในครั้งเดียว พร้อมรายงาน Unicode U+XXXX และ CP874 hex (คลิก Show Details); ไม่แปลงเป็น TTF แบบเงียบ ๆ
- ภาษาอังกฤษ/ไทยใน SHX ที่มี glyph ภาษาไทย; โหมดอ่านรหัส `Unicode`, `CP874` หรือ Auto
- รองรับ multiline, align L/C/R, width factor, character tracking, line spacing, rotation และ Preview
- Model: สร้าง Group ของ edge จริง บน Layer `GO | SHX Stroke Text` เลือก/ย้ายได้, บันทึกใน `.igz`, Undo/Redo, แก้ไขค่าจาก Load selected/Update Selected
- **รักษาพิกัดหลัง Move:** Load selected text อ่านพิกัด X/Y/Z ปัจจุบันจากเส้นจริง ก่อน Update, ไม่ย้อนกลับ insertion เก่าที่บันทึกใน metadata; ปุ่ม Update จะรักษาความละเอียดพิกัดไว้ถ้าผู้ใช้ไม่ได้แก้ช่องนั้น
- **Double-click Edit:** ขณะใช้เครื่องมือ Select ดับเบิลคลิก Group ที่สร้างโดย GO SHX เพื่อเปิด dialog แก้ไข; ไม่กระทบ Group อื่น และปิดได้ด้วย checkbox. มีเมนู Edit Selected Stroke Text และเมนูคลิกขวาสำรอง
- **ภาษาไทย:** เครื่องหมาย `Mn` ที่มี Unicode combining class เป็นศูนย์ (เช่น `ิ` และ `ั`) ไม่ถูกนับเป็นตัวอักษรที่มีระยะ advance เพิ่มผิด ๆ เหมือน v0.1.0
- Sheet Composer: แปลงเป็น `FormaItem(kind="linea")` ทีละท่อนบนหน้ากระดาษจริง บนหน่วย mm รองรับการพิมพ์ PDF ผ่าน native sheet renderer; ใช้ปุ่ม Export SHX sheet DXF เพื่อส่งเฉพาะเส้น SHX ออกเป็น DXF แยกต่างหาก และ Composer Undo; เลือกข้อความเดิมใน combo เพื่อ Update/Delete ได้
- บันทึกต้นฉบับและพารามิเตอร์ไว้ใน `group.ext` (Model) และ `scene.plugin_data` (Sheet) หากไฟล์ SHX ต้นทางหาย geometry ที่เคยบันทึกยังอยู่ แต่แก้ไขใหม่ไม่ได้จนกว่าจะเลือกฟอนต์อีกครั้ง
- รองรับ **v0.1.0 Group เดิม**: reconstruct geometry ต้นฉบับจากไฟล์ SHX เดิมเพื่อหาการเลื่อนพิกัดครั้งแรก; หลัง Update เป็น v0.2.0 จะมี `reference_bounds` และสถิติ geometry เก็บไว้ ไม่ต้อง reconstruct ทุกครั้ง

## อัปเกรดจาก v0.1.0 โดยไม่ต้องลบข้อความที่สร้างไว้

1. **สำรองไฟล์ `.igz`** ก่อนเริ่ม (และปิด IngeTrazo)
2. ติดตั้งโฟลเดอร์ `go_shx_stroke_text` จาก Plugin ZIP ใหม่ทับของเดิม แล้วเริ่ม IngeTrazo ใหม่
3. เปิด `.igz` เดิมและใช้ Select เลือกข้อความ Group ที่เคยสร้าง
4. กด **Load selected text** (หรือ **ดับเบิลคลิก Group**) เพื่อโหลดข้อความและพิกัดหลัง Move จริง
5. แก้ข้อความ, ขนาด, มุม หรือฟอนต์ตามต้องการ → **Check all glyphs** → **Preview strokes** → **Update Selected**
6. เปรียบเทียบตำแหน่งก่อน-หลัง Update; กด Ctrl+Z เพื่อเรียก Group เก่ากลับหากไม่ถูกใจ

> สำหรับ Group v0.1.0 ที่เคย Move มาแล้ว จำเป็นต้องเข้าถึง **ไฟล์ฟอนต์ SHX เดิม** เพื่อคำนวณตำแหน่งอ้างอิงครั้งแรก หลัง Update เป็น v0.2.0 จะไม่ต้องใช้ฟอนต์เดิมเพื่อ *อ่านพิกัด* อีก แต่การสร้างข้อความใหม่ยังต้องใช้ไฟล์ SHX ที่เลือกได้จริง

## วิธีทดสอบง่าย ๆ

- Model: `ABCabc123` ขนาด 0.30 m, plane XY, insertion (0,0,0) → Create → Move → Ctrl+Z → Redo
- หากมี SHX ภาษาไทย: `กขค ABC123 ภาษาไทย` → Preview แล้วตรวจวรรณยุกต์ที่ตำแหน่งจริงในแบบ
- Sheet: สร้าง A4 Sheet → กลับหน้าต่างปลั๊กอินเลือก Sheet, Height 3.5 mm, X 25 mm, Y 30 mm → Create. ตรวจ PDF มีเส้น Vector; กด Export sheet SHX DXF เพื่อส่งเฉพาะข้อความ SHX เป็น DXF → Composer Undo/Redo → Save/Reload .igz
- ลองเปิดเอกสารอื่นแล้วกลับมาปรับข้อความที่เลือกใหม่ รวมถึงสลับ sheet ระหว่างแก้ไข

## ข้อจำกัด v0.2.0

1. `BIGFONT` SHX ที่ ezdxf ไม่รองรับจะอ่านไม่ได้ (จะขึ้น error ไม่แปลงเป็น TTF แทน)
2. SHX ไม่ใช่ระบบจัดรูปคำ Unicode แบบ OpenType; สระ/วรรณยุกต์ภาษาไทยอาจไม่ตรงในบางฟอนต์ จึงมีเพียงการปรับจุดเกาะอย่างง่าย ต้องตรวจภาพจริงก่อนใช้แบบก่อสร้าง
3. การแปลงตัวอักษรเป็น Line item ของ Sheet ทำให้ข้อความยาวมีจำนวนวัตถุมาก จำกัด 2,500 ท่อน / รายการเพื่อป้องกัน Sheet ช้า; Model จำกัด 16,000 ท่อน
4. Sheet text เป็น vector line set ไม่ใช่ TEXT entity ที่แก้ในโปรแกรม CAD ได้โดยตรง; แก้ต้นฉบับผ่านหน้าต่าง GO SHX
5. **ข้อจำกัด DXF:** คำสั่ง Export view as DXF ของ IngeTrazo ส่งออกเฉพาะโมเดลใน Frame ไม่ได้ส่ง Paper-space annotations บน Sheet ดังนั้นข้อความ SHX ในหน้ากระดาษต้องใช้ปุ่ม **Export sheet SHX DXF** ของส่วนเสริม (เฉพาะเส้น GO SHX บนกระดาษ). ข้อความที่สร้างใน Model จะเข้า DXF Export view ตามการมองเห็นของ Frame ตามปกติ
6. **ทดสอบโค้ดอัตโนมัติผ่าน 20 กรณีแล้ว** แต่ยังไม่ได้ทดสอบ end-to-end บน IngeTrazo Windows เครื่องผู้ใช้ กับไฟล์ `THAISIMP.SHX` ตัวจริง; เป็น Beta สำหรับติดตั้งทดลอง
7. ไม่ได้แจก/ฝังฟอนต์ SHX ของ Autodesk หรือผู้ขายรายอื่นเพราะอาจติดลิขสิทธิ์

8. ฟอนต์ SHX ที่ไม่มี glyph `๑` (U+0E51) จริง **ไม่สามารถทำให้มีรูปเลขไทยได้ด้วยการสลับ CP874 อย่างเดียว**. Check all glyphs จะรายงานครบทุกตัวที่ไม่มี ผู้ใช้ต้องเลือก SHX ที่รองรับจริงหรือแก้เนื้อหา (เช่น เลือก `1` แทน `๑`) ด้วยตนเอง; โปรแกรมไม่เปลี่ยนเนื้อหาเงียบ ๆ.
9. การตรวจจับตำแหน่งอัตโนมัติรองรับ **pure translation (Move)**; การ Rotate/Scale หรือแก้ไข shape ภายใน Group จากเครื่องมือภายนอกอาจไม่สามารถย้อนหาพิกัดกำเนิดได้อย่างปลอดภัย จึงจะบล็อกการ Update แทนการเขียนทับ. Group ที่แปลงเป็น Component แบบมี transform ไม่รองรับการแก้ข้อความในรุ่นนี้.
10. การดับเบิลคลิกต้องใช้ **Select tool** บนหน้า Model (ไม่ใช่ขณะอยู่ภายใน Group Edit) และไม่มี Shift/Ctrl กดค้าง. เครื่องมืออื่น ๆ ยังคงทำงานตามปกติ; หาก shortcut มีปัญหาใช้ Extensions → GO SHX Stroke Text → Edit Selected Stroke Text แทน.

**หลักฐาน API:** `https://github.com/ingelibre/ingetrazo/blob/main/docs/plugins.md`, `core/group.py`, `core/composition.py`, `views/composer.py`, และ `ezdxf.fonts.shapefile`.

