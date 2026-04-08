#!/usr/bin/env node
/**
 * Embedding API Base64 格式测试脚本
 *
 * 使用 OpenAI JavaScript 库测试 embedding 服务的 base64 输出格式
 *
 * 使用方法:
 *   npm install openai
 *   node tests/test-embedding-base64.js
 *
 * 或者使用 npx:
 *   npx openai@^4.0.0 (先安装依赖)
 */

const OpenAI = require('openai');

// 配置
const EMBEDDING_API_URL = 'http://localhost:8091/v1/';
const TEST_TEXTS = [
    '你好，世界',
    '机器学习是人工智能的一个分支',
    '今天天气真好，适合出去散步',
];

// 创建 OpenAI 客户端
const client = new OpenAI({
    apiKey: 'not-needed', // embedding 服务不需要 API key
    baseURL: EMBEDDING_API_URL,
});

/**
 * 将 base64 编码的字符串解码为 float32 数组
 * @param {string} base64String - base64 编码的字符串
 * @returns {number[]} - float32 数组
 */
function decodeBase64Embedding(base64String) {
    const buffer = Buffer.from(base64String, 'base64');
    const floatArray = [];

    // 每 4 个字节是一个 float32
    for (let i = 0; i < buffer.length; i += 4) {
        const float = buffer.readFloatLE(i);
        floatArray.push(float);
    }

    return floatArray;
}

/**
 * 验证 embedding 数据结构
 * @param {Object} embedding - embedding 对象
 * @param {string} encodingFormat - 期望的编码格式
 * @returns {boolean} - 验证是否通过
 */
function validateEmbeddingStructure(embedding, encodingFormat) {
    const errors = [];

    // 检查必要字段
    if (!embedding.hasOwnProperty('embedding')) {
        errors.push('缺少 embedding 字段');
    }
    if (!embedding.hasOwnProperty('index')) {
        errors.push('缺少 index 字段');
    }
    if (!embedding.hasOwnProperty('object')) {
        errors.push('缺少 object 字段');
    }

    if (errors.length > 0) {
        return { valid: false, errors };
    }

    // 验证 embedding 数据格式
    const embeddingData = embedding.embedding;

    if (encodingFormat === 'base64') {
        // 检查是否是 base64 字符串
        if (typeof embeddingData !== 'string') {
            errors.push(`base64 格式下 embedding 应该是字符串，实际是 ${typeof embeddingData}`);
        } else {
            // 验证 base64 格式
            const base64Regex = /^[A-Za-z0-9+/]+={0,2}$/;
            if (!base64Regex.test(embeddingData)) {
                errors.push('embedding 不是有效的 base64 格式');
            } else {
                // 尝试解码
                try {
                    const decoded = decodeBase64Embedding(embeddingData);
                    if (decoded.length === 0) {
                        errors.push('解码后的 embedding 数组为空');
                    }
                    if (decoded.some(v => typeof v !== 'number' || isNaN(v))) {
                        errors.push('解码后包含非数字或 NaN 值');
                    }
                } catch (e) {
                    errors.push(`base64 解码失败：${e.message}`);
                }
            }
        }
    } else if (encodingFormat === 'float') {
        // 检查是否是浮点数数组
        if (!Array.isArray(embeddingData)) {
            errors.push(`float 格式下 embedding 应该是数组，实际是 ${typeof embeddingData}`);
        } else if (embeddingData.length === 0) {
            errors.push('embedding 数组为空');
        } else if (embeddingData.some(v => typeof v !== 'number' || isNaN(v))) {
            errors.push('embedding 包含非数字或 NaN 值');
        }
    }

    return {
        valid: errors.length === 0,
        errors,
        dimension: Array.isArray(embeddingData) ? embeddingData.length :
                   (typeof embeddingData === 'string' ? 'base64 encoded' : 'unknown')
    };
}

/**
 * 测试单个文本的 embedding
 * @param {string} text - 输入文本
 * @param {string} encodingFormat - 编码格式
 */
async function testEmbedding(text, encodingFormat = 'base64') {
    console.log(`\n测试文本："${text}"`);
    console.log(`编码格式：${encodingFormat}`);
    console.log('-'.repeat(60));

    try {
        const response = await client.embeddings.create({
            model: 'embedding',
            input: text,
            encoding_format: encodingFormat,
        });

        console.log(`响应状态：✓ 成功`);
        console.log(`模型：${response.model}`);
        console.log(`数据条数：${response.data.length}`);

        // 验证每条 embedding 数据
        let allValid = true;
        for (const item of response.data) {
            const validation = validateEmbeddingStructure(item, encodingFormat);

            if (validation.valid) {
                console.log(`  [${item.index}] ✓ 格式验证通过`);

                // 显示 embedding 信息
                if (encodingFormat === 'base64') {
                    // 解码并显示维度
                    const decoded = decodeBase64Embedding(item.embedding);
                    console.log(`       维度：${decoded.length}`);
                    console.log(`       前 5 个值：[${decoded.slice(0, 5).map(v => v.toFixed(6)).join(', ')}...]`);

                    // 验证向量范数（归一化向量的范数应接近 1）
                    const norm = Math.sqrt(decoded.reduce((sum, v) => sum + v * v, 0));
                    console.log(`       向量范数：${norm.toFixed(6)} (应接近 1.0)`);
                } else {
                    console.log(`       维度：${item.embedding.length}`);
                    console.log(`       前 5 个值：[${item.embedding.slice(0, 5).map(v => v.toFixed(6)).join(', ')}...]`);
                }
            } else {
                console.log(`  [${item.index}] ✗ 格式验证失败:`);
                validation.errors.forEach(err => console.log(`       - ${err}`));
                allValid = false;
            }
        }

        // 验证响应结构
        if (!response.hasOwnProperty('object')) {
            console.log('  ✗ 响应缺少 object 字段');
            allValid = false;
        } else {
            console.log(`  响应 object 类型：${response.object}`);
        }

        if (!response.hasOwnProperty('usage')) {
            console.log('  ✗ 响应缺少 usage 字段');
            allValid = false;
        } else {
            console.log(`  Usage: prompt_tokens=${response.usage.prompt_tokens}, total_tokens=${response.usage.total_tokens}`);
        }

        return allValid;

    } catch (error) {
        console.log(`✗ 请求失败：${error.message}`);
        if (error.response) {
            console.log(`  状态码：${error.response.status}`);
            console.log(`  响应：${JSON.stringify(error.response.data)}`);
        }
        return false;
    }
}

/**
 * 批量测试
 */
async function runTests() {
    console.log('='.repeat(60));
    console.log('Embedding API Base64 格式测试');
    console.log(`API 地址：${EMBEDDING_API_URL}`);
    console.log('='.repeat(60));

    const results = {
        base64: { passed: 0, failed: 0 },
        float: { passed: 0, failed: 0 },
    };

    // 测试 base64 格式（默认）
    console.log('\n【测试组 1】Base64 编码格式测试');
    console.log('(不指定 encoding_format 参数，使用默认值)');
    for (const text of TEST_TEXTS) {
        const passed = await testEmbedding(text, 'base64');
        if (passed) {
            results.base64.passed++;
        } else {
            results.base64.failed++;
        }
    }

    // 测试 float 格式（显式指定）
    console.log('\n【测试组 2】Float 编码格式测试');
    console.log('(显式指定 encoding_format=float)');
    for (const text of TEST_TEXTS) {
        const passed = await testEmbedding(text, 'float');
        if (passed) {
            results.float.passed++;
        } else {
            results.float.failed++;
        }
    }

    // 汇总结果
    console.log('\n' + '='.repeat(60));
    console.log('测试结果汇总');
    console.log('='.repeat(60));
    console.log(`Base64 格式：${results.base64.passed} 通过，${results.base64.failed} 失败`);
    console.log(`Float 格式：  ${results.float.passed} 通过，${results.float.failed} 失败`);

    const totalPassed = results.base64.passed + results.float.passed;
    const totalFailed = results.base64.failed + results.float.failed;

    if (totalFailed === 0) {
        console.log('\n✓ 所有测试通过！');
        process.exit(0);
    } else {
        console.log(`\n✗ ${totalFailed} 个测试失败`);
        process.exit(1);
    }
}

// 运行测试
runTests().catch(err => {
    console.error('测试执行失败:', err);
    process.exit(1);
});
