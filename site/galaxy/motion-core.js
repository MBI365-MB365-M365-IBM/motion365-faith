async function motionResolve(input) {
    const response = await fetch('/api/core/v1/motion/resolve', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(input)
    });

    if (!response.ok) {
        throw new Error(`Motion Core returned HTTP ${response.status}`);
    }

    return response.json();
}
