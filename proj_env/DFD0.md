# DFD Level 0 — Syllabus Studio & Student Manager

```mermaid
flowchart LR
  %% External entities
  Student([Student])
  Instructor([Instructor])
  ExternalSyllabus([External Syllabus Source])

  %% Processes
  SyllabusAnalyzer[[Syllabus Analyzer (Process 1)]]
  StudentManager[[Student Manager (Process 2)]]
  PDFProcessor[[PDF Extractor/Parser]]
  ReportGen[[DPP / Report Generator]]

  %% Data stores
  StudentDB[(Student DB)]
  SyllabusDB[(Syllabus DB)]

  %% Flows
  Student -->|upload syllabus / request analysis| SyllabusAnalyzer
  ExternalSyllabus -->|provide syllabus files| SyllabusAnalyzer
  SyllabusAnalyzer -->|parsed syllabus data| SyllabusDB
  SyllabusAnalyzer -->|analysis results / insights| ReportGen
  ReportGen -->|deliver report / DPP| Student

  Student -->|manage tasks / progress| StudentManager
  Instructor -->|assign tasks / review| StudentManager
  StudentManager -->|read/write progress| StudentDB
  StudentManager -->|request syllabus analysis| SyllabusAnalyzer

  PDFProcessor -->|extract text| SyllabusAnalyzer
  SyllabusAnalyzer -->|store findings| StudentDB

  %% Notes
  classDef entity fill:#f9f,stroke:#333,stroke-width:1px;
  class Student,Instructor,ExternalSyllabus entity;
  classDef process fill:#bbf,stroke:#333,stroke-width:1px;
  class SyllabusAnalyzer,StudentManager,PDFProcessor,ReportGen process;
  classDef datastore fill:#fee,stroke:#333,stroke-width:1px;
  class StudentDB,SyllabusDB datastore;
```

Notes:
- This Level-0 DFD shows the system as two main processes: `Syllabus Analyzer` and `Student Manager`.
- External actors are `Student`, `Instructor`, and external syllabus sources (e.g., university websites, uploaded PDFs).
- Data stores include the student database and the syllabus database where parsed syllabi and analysis results are kept.

If you'd like, I can export this to PNG/SVG or insert it into a Word/PDF document for you.