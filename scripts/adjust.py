import pandas as pd
import json
import os

# 학기별 엑셀 파일 정보 (파일명, 연도, 학기)
excel_files = [
    ("개설교과목정보/개설교과목정보(2023-1).xlsx", 2023, 1),
    ("개설교과목정보/개설교과목정보(2023-2).xlsx", 2023, 2),
    ("개설교과목정보/개설교과목정보(2024-1).xlsx", 2024, 1),
    ("개설교과목정보/개설교과목정보(2024-2).xlsx", 2024, 2),
    ("개설교과목정보/개설교과목정보(2025-1).xlsx", 2025, 1),
    ("개설교과목정보/개설교과목정보(2025-하계학기).xlsx", 2025, 3),  # 하계학기는 semester=3으로 가정
]

# 엑셀에서 추출할 컬럼명(엑셀 파일에 따라 다를 수 있음, 필요시 수정)
col_major = "학과"
col_code = "과목번호"
col_name = "과목명"
col_section = "분반"

# 엑셀 정보 매핑: {(year, semester, major, section): (code, name)}
course_map = {}

for file, year, semester in excel_files:
    if not os.path.exists(file):
        continue
    df = pd.read_excel(file, dtype=str)
    for _, row in df.iterrows():
        key = (year, semester, row[col_major], str(row[col_section]).zfill(2))
        value = (row[col_code], row[col_name])
        course_map[key] = value

# JSON 파일 불러오기
with open("academic_data_final_with_grades_filtered.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 과목 정보가 들어있는 리스트 찾기 (예시: data["courses"] 또는 data["subjects"] 등)
# 아래는 과목 정보가 data["courses"]에 있다고 가정
if "courses" in data:
    course_list = data["courses"]
else:
    # 과목 정보가 students 리스트 이후에 있을 수 있으니, students 리스트 이후의 첫 리스트를 찾음
    for k, v in data.items():
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and "code" in v[0] and "name" in v[0]:
            course_list = v
            break

# 과목 정보 수정
for course in course_list:
    key = (
        course.get("year"),
        course.get("semester"),
        course.get("major"),
        str(course.get("section")).zfill(2)
    )
    if key in course_map:
        course["code"], course["name"] = course_map[key]

# 결과 저장
with open("academic_data_final_with_grades_filtered_UPDATED.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("완료! academic_data_final_with_grades_filtered_UPDATED.json 파일을 확인하세요.")