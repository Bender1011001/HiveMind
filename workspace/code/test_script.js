// Test script to verify JavaScript execution
const numbers = [1, 2, 3, 4, 5];
const sum = numbers.reduce((a, b) => a + b, 0);
const avg = sum / numbers.length;

const output = `
Code Execution Test Results:
---------------------------
Time of execution: ${new Date().toLocaleString()}
Test calculations:
- Sum of numbers [${numbers}]: ${sum}
- Average: ${avg}
- Node.js version: ${process.version}
`;

console.log(output);
