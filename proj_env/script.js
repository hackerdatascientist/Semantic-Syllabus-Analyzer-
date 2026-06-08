async function analyzeData() {
    const syllabus = document.getElementById('syllabusFile').files[0];
    const book = document.getElementById('bookFile').files[0];
    const loader = document.getElementById('loader');
    const resultsSection = document.getElementById('resultsSection');
    const outputArea = document.getElementById('output-area');
    const semanticArea = document.getElementById('semantic-area');

    if (!syllabus || !book) {
        alert("ACCESS DENIED: Please upload both files.");
        return;
    }

    // Show loader
    loader.style.display = 'block';
    resultsSection.style.display = 'none';

    const formData = new FormData();
    formData.append('syllabus', syllabus);
    formData.append('book', book);

    try {
        // CALLING FASTAPI BACKEND
        const response = await fetch('http://127.0.0.1:8000/analyze', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        
        if (response.ok) {
            const semanticData = JSON.parse(result.data);
            
            // Populate Human View
            outputArea.innerHTML = `<h3>Generated Notes & Quiz</h3>` + 
                JSON.stringify(semanticData, null, 2); // You can format this further later
            
            // Populate Semantic View
            semanticArea.textContent = JSON.stringify(semanticData, null, 2);
            
            loader.style.display = 'none';
            resultsSection.style.display = 'block';
        } else {
            alert("ERROR: " + result.detail);
        }
    } catch (error) {
        console.error(error);
        alert("SYSTEM_CRASH: Could not connect to backend server.");
        loader.style.display = 'none';
    }
}

function showTab(type) {
    const human = document.getElementById('output-area');
    const semantic = document.getElementById('semantic-area');
    const btns = document.querySelectorAll('.tab-btn');

    if (type === 'human') {
        human.style.display = 'block';
        semantic.style.display = 'none';
        btns[0].classList.add('active');
        btns[1].classList.remove('active');
    } else {
        human.style.display = 'none';
        semantic.style.display = 'block';
        btns[1].classList.add('active');
        btns[0].classList.remove('active');
    }
}