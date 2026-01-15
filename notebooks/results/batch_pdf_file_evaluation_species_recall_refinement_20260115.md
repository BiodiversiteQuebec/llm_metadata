# Batch PDF File-Based Extraction Evaluation

Evaluate PDF-based metadata extraction using OpenAI's native File API across open access Fuster validation samples.

**Approach:**
- Filter to open access PDFs only (via OpenAlex `is_oa` flag)
- Upload raw PDFs to OpenAI File API
- Use GPT-5-mini with native PDF understanding (text + visual analysis)
- Custom `PDF_SYSTEM_MESSAGE` optimized for document structure
- Compare against manually annotated ground truth
- Use `DatasetFeaturesNormalized` for ground truth validation

**Key Differences from Section-Based Pipeline:**
- No GROBID parsing required
- OpenAI processes both text AND images from each page
- Better for tables, figures, and visual content
- Higher token usage (text + image per page)

    c:\Users\beav3503\AppData\Local\miniforge3\envs\llm\Lib\site-packages\pydantic\json_schema.py:2448: PydanticJsonSchemaWarning: Default value <class 'llm_metadata.schemas.abstract_metadata.DatasetAbstractMetadata'> is not JSON serializable; excluding default from JSON schema [non-serializable-default]
      warnings.warn(message, PydanticJsonSchemaWarning)
    c:\Users\beav3503\AppData\Local\miniforge3\envs\llm\Lib\site-packages\pydantic\json_schema.py:2448: PydanticJsonSchemaWarning: Default value <class 'llm_metadata.schemas.abstract_metadata.DatasetAbstractMetadata'> is not JSON serializable; excluding default from JSON schema [non-serializable-default]
      warnings.warn(message, PydanticJsonSchemaWarning)
    

    Project root: c:\Users\beav3503\dev\llm_metadata
    PDF directory: c:\Users\beav3503\dev\llm_metadata\data\pdfs\fuster
    Manifest exists: True
    Ground truth exists: True
    

## Step 1: Load Manifest and Ground Truth

Map dataset DOIs to article DOIs and load ground truth annotations.

    Manifest: 75 total rows
    Downloaded PDFs: 70
    DOI mappings: 70
    




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>article_doi</th>
      <th>dataset_doi</th>
      <th>downloaded_pdf_path</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>1</th>
      <td>10.1093/jhered/esx103</td>
      <td>10.5061/dryad.121sk</td>
      <td>fuster\10.1093_jhered_esx103.pdf</td>
    </tr>
    <tr>
      <th>2</th>
      <td>10.1371/journal.pone.0128238</td>
      <td>10.5061/dryad.1771t</td>
      <td>fuster\10.1371_journal.pone.0128238.pdf</td>
    </tr>
    <tr>
      <th>3</th>
      <td>10.1371/journal.pone.0073695</td>
      <td>10.5061/dryad.1cc4v</td>
      <td>fuster\10.1371_journal.pone.0073695.pdf</td>
    </tr>
    <tr>
      <th>4</th>
      <td>10.1002/ece3.4685</td>
      <td>10.5061/dryad.24q6q70</td>
      <td>fuster\10.1002_ece3.4685.pdf</td>
    </tr>
    <tr>
      <th>5</th>
      <td>10.1639/0007-2745-119.1.008</td>
      <td>10.5061/dryad.24rj8</td>
      <td>fuster\10.1639_0007-2745-119.1.008.pdf</td>
    </tr>
  </tbody>
</table>
</div>



    Ground truth: 418 total rows
    Ground truth with matched PDFs: 70
    




<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>dataset_doi</th>
      <th>article_doi</th>
      <th>data_type</th>
      <th>species</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2</th>
      <td>10.5061/dryad.121sk</td>
      <td>10.1093/jhered/esx103</td>
      <td>EBV genetic analysis</td>
      <td>Glyptemys insculpta</td>
    </tr>
    <tr>
      <th>4</th>
      <td>10.5061/dryad.1771t</td>
      <td>10.1371/journal.pone.0128238</td>
      <td>density</td>
      <td>raccoons, striped skunks</td>
    </tr>
    <tr>
      <th>6</th>
      <td>10.5061/dryad.1cc4v</td>
      <td>10.1371/journal.pone.0073695</td>
      <td>presence only</td>
      <td>Rangifer tarandus caribou</td>
    </tr>
    <tr>
      <th>7</th>
      <td>10.5061/dryad.24q6q70</td>
      <td>10.1002/ece3.4685</td>
      <td>other</td>
      <td>Rangifer tarandus caribou</td>
    </tr>
    <tr>
      <th>8</th>
      <td>10.5061/dryad.24rj8</td>
      <td>10.1639/0007-2745-119.1.008</td>
      <td>genetic analysis</td>
      <td>Aspicilia bicensis</td>
    </tr>
  </tbody>
</table>
</div>



## Step 2: Filter to Open Access PDFs Only

Query OpenAlex to identify open access papers and get PDF URLs where available.

    Querying OpenAlex for open access status...
    
    OpenAlex query complete: 70 records
    

    Open access papers: 44 out of 70
    
    Open Access Status Breakdown:
    oa_status
    gold         25
    closed       19
    bronze       17
    not_found     7
    green         2
    Name: count, dtype: int64
    
    OA papers with direct PDF URL: 39
    OA papers requiring local file: 5
    

    Successfully validated: 44 records
    Validation errors: 0 records
    

## Step 3: Configure PDF File Pipeline

Set up PDF file-based extraction with OpenAI's native PDF support and custom system prompt.

    Improved species prompt defined
    Prompt length: 4862 characters
    

    PDF File Pipeline Configuration:
      Model: gpt-5-mini
      Reasoning: {'effort': 'low'}
      Max output tokens: 4096
      Extraction schema: DatasetFeatures
      Mode: Native PDF (OpenAI File API)
    
    System Prompt Preview (first 300 chars):
      You are EcodataGPT, a structured data extraction engine for scientific PDF analysis.
    
    Goal: Extract biodiversity dataset features from the provided PDF document into the provided schema.
    
    ## PDF Document Analysis
    
    This PDF has been processed to provide both:
    1. **Extracted text** from each page for ...
    

## Step 4: Run PDF File-Based Extraction

Process all open access PDFs through OpenAI's File API.

    PDFInputRecords created: 44
    All records will use local PDF files (native PDF mode)
    

    Running PDF file-based extraction on 44 papers...
    Output manifest: c:\Users\beav3503\dev\llm_metadata\artifacts\pdf_file_results\pdf_file_results_20260115_154837.csv
    
      
    Completed: 39 success, 5 failed
    Total cost: $0.5066
    Saved output manifest to c:\Users\beav3503\dev\llm_metadata\artifacts\pdf_file_results\pdf_file_results_20260115_154837.csv (44 records)
   
    Extraction method breakdown:
    extraction_method
    openai_file_api    39
    Name: count, dtype: int64
    

## Step 5: Prepare Extractions for Evaluation

Convert extraction results to Pydantic models for evaluation.

    Valid predictions: 39
    Common DOIs for evaluation: 39
    

## Step 6: Evaluate PDF File-Based Extraction

Compare PDF file-based extractions against ground truth using evaluation framework.

    PDF FILE-BASED Extraction Metrics:
    ======================================================================
    


<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>field</th>
      <th>tp</th>
      <th>fp</th>
      <th>fn</th>
      <th>tn</th>
      <th>n</th>
      <th>precision</th>
      <th>recall</th>
      <th>f1</th>
      <th>accuracy</th>
      <th>exact_match_rate</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>data_type</td>
      <td>25</td>
      <td>113</td>
      <td>22</td>
      <td>0</td>
      <td>39</td>
      <td>0.181159</td>
      <td>0.531915</td>
      <td>0.270270</td>
      <td>0.641026</td>
      <td>0.000000</td>
    </tr>
    <tr>
      <th>1</th>
      <td>geospatial_info_dataset</td>
      <td>16</td>
      <td>163</td>
      <td>5</td>
      <td>0</td>
      <td>39</td>
      <td>0.089385</td>
      <td>0.761905</td>
      <td>0.160000</td>
      <td>0.410256</td>
      <td>0.000000</td>
    </tr>
    <tr>
      <th>2</th>
      <td>spatial_range_km2</td>
      <td>17</td>
      <td>6</td>
      <td>11</td>
      <td>9</td>
      <td>39</td>
      <td>0.739130</td>
      <td>0.607143</td>
      <td>0.666667</td>
      <td>0.666667</td>
      <td>0.666667</td>
    </tr>
    <tr>
      <th>6</th>
      <td>species</td>
      <td>50</td>
      <td>153</td>
      <td>12</td>
      <td>0</td>
      <td>39</td>
      <td>0.246305</td>
      <td>0.806452</td>
      <td>0.377358</td>
      <td>1.282051</td>
      <td>0.512821</td>
    </tr>
    <tr>
      <th>5</th>
      <td>temp_range_f</td>
      <td>26</td>
      <td>8</td>
      <td>7</td>
      <td>5</td>
      <td>39</td>
      <td>0.764706</td>
      <td>0.787879</td>
      <td>0.776119</td>
      <td>0.794872</td>
      <td>0.794872</td>
    </tr>
    <tr>
      <th>4</th>
      <td>temp_range_i</td>
      <td>29</td>
      <td>5</td>
      <td>4</td>
      <td>5</td>
      <td>39</td>
      <td>0.852941</td>
      <td>0.878788</td>
      <td>0.865672</td>
      <td>0.871795</td>
      <td>0.871795</td>
    </tr>
    <tr>
      <th>3</th>
      <td>temporal_range</td>
      <td>1</td>
      <td>36</td>
      <td>32</td>
      <td>2</td>
      <td>39</td>
      <td>0.027027</td>
      <td>0.030303</td>
      <td>0.028571</td>
      <td>0.076923</td>
      <td>0.076923</td>
    </tr>
  </tbody>
</table>
</div>


    
    Aggregate Metrics:
    ==================================================
    Metric                              Value
    --------------------------------------------------
    Micro Precision                     0.253
    Micro Recall                        0.638
    Micro F1                            0.362
    Macro F1                            0.449
    Records Evaluated                      39
    ==================================================
    

## Step 7: Per-Field Analysis

    Per-Field Metrics:
    


<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>field</th>
      <th>precision</th>
      <th>recall</th>
      <th>f1</th>
      <th>tp</th>
      <th>fp</th>
      <th>fn</th>
      <th>exact_match_rate</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>data_type</td>
      <td>0.181</td>
      <td>0.532</td>
      <td>0.270</td>
      <td>25</td>
      <td>113</td>
      <td>22</td>
      <td>0.000</td>
    </tr>
    <tr>
      <th>1</th>
      <td>geospatial_info_dataset</td>
      <td>0.089</td>
      <td>0.762</td>
      <td>0.160</td>
      <td>16</td>
      <td>163</td>
      <td>5</td>
      <td>0.000</td>
    </tr>
    <tr>
      <th>2</th>
      <td>spatial_range_km2</td>
      <td>0.739</td>
      <td>0.607</td>
      <td>0.667</td>
      <td>17</td>
      <td>6</td>
      <td>11</td>
      <td>0.667</td>
    </tr>
    <tr>
      <th>3</th>
      <td>temporal_range</td>
      <td>0.027</td>
      <td>0.030</td>
      <td>0.029</td>
      <td>1</td>
      <td>36</td>
      <td>32</td>
      <td>0.077</td>
    </tr>
    <tr>
      <th>4</th>
      <td>temp_range_i</td>
      <td>0.853</td>
      <td>0.879</td>
      <td>0.866</td>
      <td>29</td>
      <td>5</td>
      <td>4</td>
      <td>0.872</td>
    </tr>
    <tr>
      <th>5</th>
      <td>temp_range_f</td>
      <td>0.765</td>
      <td>0.788</td>
      <td>0.776</td>
      <td>26</td>
      <td>8</td>
      <td>7</td>
      <td>0.795</td>
    </tr>
    <tr>
      <th>6</th>
      <td>species</td>
      <td>0.246</td>
      <td>0.806</td>
      <td>0.377</td>
      <td>50</td>
      <td>153</td>
      <td>12</td>
      <td>0.513</td>
    </tr>
  </tbody>
</table>
</div>


    
    Best performing field: temp_range_i (F1=0.866)
    Worst performing field: temporal_range (F1=0.029)
    

    Per-record, per-field results (mismatches highlighted):
    
    Total mismatches: 159
    


<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>record_id</th>
      <th>field</th>
      <th>true_value</th>
      <th>pred_value</th>
      <th>match</th>
      <th>tp</th>
      <th>fp</th>
      <th>fn</th>
      <th>tn</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>10.5061/dryad.121sk</td>
      <td>data_type</td>
      <td>[genetic_analysis]</td>
      <td>[genetic_analysis, abundance, time_series]</td>
      <td>False</td>
      <td>1</td>
      <td>2</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>1</th>
      <td>10.5061/dryad.121sk</td>
      <td>geospatial_info_dataset</td>
      <td>None</td>
      <td>[site, administrative_units]</td>
      <td>False</td>
      <td>0</td>
      <td>2</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>3</th>
      <td>10.5061/dryad.121sk</td>
      <td>temporal_range</td>
      <td>2006-2007</td>
      <td>2006–2007</td>
      <td>False</td>
      <td>0</td>
      <td>1</td>
      <td>1</td>
      <td>0</td>
    </tr>
    <tr>
      <th>7</th>
      <td>10.5061/dryad.1771t</td>
      <td>data_type</td>
      <td>[density]</td>
      <td>[abundance, density, distribution]</td>
      <td>False</td>
      <td>1</td>
      <td>2</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>8</th>
      <td>10.5061/dryad.1771t</td>
      <td>geospatial_info_dataset</td>
      <td>[sample]</td>
      <td>[sample, site, administrative_units, maps, geo...</td>
      <td>False</td>
      <td>1</td>
      <td>4</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>...</th>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
      <td>...</td>
    </tr>
    <tr>
      <th>262</th>
      <td>10.5061/dryad.t11f5</td>
      <td>temporal_range</td>
      <td>2007</td>
      <td>8 June 2007 to 15 August 2007</td>
      <td>False</td>
      <td>0</td>
      <td>1</td>
      <td>1</td>
      <td>0</td>
    </tr>
    <tr>
      <th>265</th>
      <td>10.5061/dryad.t11f5</td>
      <td>species</td>
      <td>[10 fish species]</td>
      <td>[White sucker (Catostomus commersoni), Rock ba...</td>
      <td>False</td>
      <td>0</td>
      <td>10</td>
      <td>1</td>
      <td>0</td>
    </tr>
    <tr>
      <th>266</th>
      <td>10.5061/dryad.xksn02vb9</td>
      <td>data_type</td>
      <td>[other]</td>
      <td>[traits, genetic_analysis]</td>
      <td>False</td>
      <td>0</td>
      <td>2</td>
      <td>1</td>
      <td>0</td>
    </tr>
    <tr>
      <th>267</th>
      <td>10.5061/dryad.xksn02vb9</td>
      <td>geospatial_info_dataset</td>
      <td>None</td>
      <td>[sample, site, administrative_units, site_ids]</td>
      <td>False</td>
      <td>0</td>
      <td>4</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>272</th>
      <td>10.5061/dryad.xksn02vb9</td>
      <td>species</td>
      <td>[white spruce]</td>
      <td>[maize, rice, sorghum, soy, spruce, switchgrass]</td>
      <td>False</td>
      <td>0</td>
      <td>6</td>
      <td>1</td>
      <td>0</td>
    </tr>
  </tbody>
</table>
<p>159 rows × 9 columns</p>
</div>


## Step 8: Cost Analysis

    
    COST ANALYSIS (PDF File-Based Extraction)
    ==================================================
    Metric                                      Value
    --------------------------------------------------
    Total PDFs Processed                           39
    Avg Input Tokens per PDF                   25,285
    Avg Output Tokens per PDF                   1,878
    --------------------------------------------------
    Total Input Tokens                        986,106
    Total Output Tokens                        73,249
    Total Cost (USD)               $           0.5066
    Avg Cost per PDF (USD)         $          0.01299
    ==================================================
    File upload extraction: 39 papers, $0.5066 total
    
