const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {Blob} = require('node:buffer');

const pageSources = new Map();
const pages = ['index.html', 'HyperBatteryHealthCalc-bat/index.html'];

function loadPage(relativePath) {
    const elements = new Map();
    const readyListeners = [];
    const timers = new Map();
    const messages = [];
    let timerId = 0;
    const downloads = {created: [], revoked: [], active: new Map(), anchors: [], attempts: [], requests: [], clickError: null};
    const entities = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0'};
    const createElement = (tagName = 'div') => ({
        tagName: tagName.toUpperCase(), style: {}, files: [], value: '', innerHTML: '',
        disabled: false, parentNode: null, children: [], listeners: new Map(),
        // DOM textContent has no layout-derived line breaks and retains button text.
        // Only production htmlToPlainText may add separators or remove controls.
        get textContent() {
            return this.innerHTML.replace(/<!--[\s\S]*?-->|<[^>]*>/g, '').replace(
                /&(amp|lt|gt|quot|apos|nbsp|#\d+|#x[\da-f]+);/gi,
                (whole, entity) => entity[0] === '#'
                    ? String.fromCodePoint(entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : Number(entity.slice(1)))
                    : entities[entity.toLowerCase()]
            );
        },
        set textContent(value) {
            this.innerHTML = String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
        },
        addEventListener(type, listener) {
            if (!this.listeners.has(type)) this.listeners.set(type, []);
            this.listeners.get(type).push(listener);
        },
        dispatchEvent(event) {
            for (const listener of this.listeners.get(event.type) || []) listener.call(this, event);
            return true;
        },
        appendChild(child) { this.children.push(child); child.parentNode = this; return child; },
        removeChild(child) {
            const index = this.children.indexOf(child);
            if (index < 0) throw new Error('Cannot remove an unattached node');
            this.children.splice(index, 1);
            child.parentNode = null;
            return child;
        },
        click() {
            if (this.tagName !== 'A') {
                if (!this.disabled) this.dispatchEvent({type: 'click'});
                return;
            }
            downloads.attempts.push(this);
            if (!this.parentNode || !downloads.active.has(this.href)) throw new Error('Download anchor or URL is unavailable');
            if (downloads.clickError) throw downloads.clickError;
            downloads.requests.push({url: this.href, filename: this.download, blob: downloads.active.get(this.href)});
        }
    });
    const element = id => {
        if (!elements.has(id)) {
            const node = createElement(id.endsWith('-btn') ? 'button' : 'div');
            node.disabled = id === 'export-report-btn';
            elements.set(id, node);
        }
        return elements.get(id);
    };
    const document = {
        getElementById: element,
        body: createElement('body'),
        addEventListener(type, listener) { if (type === 'DOMContentLoaded') readyListeners.push(listener); },
        createElement(tagName) {
            const node = createElement(tagName);
            if (node.tagName === 'A') downloads.anchors.push(node);
            return node;
        }
    };
    const context = vm.createContext({
        document, Blob,
        console: {...console, warn: (...args) => messages.push(args), error: (...args) => messages.push(args)},
        URL: {
            createObjectURL(blob) {
                const url = `blob:fixture/${downloads.created.length + 1}`;
                downloads.created.push({url, blob});
                downloads.active.set(url, blob);
                return url;
            },
            revokeObjectURL(url) { downloads.revoked.push(url); downloads.active.delete(url); }
        },
        setTimeout(callback, delay, ...args) { timers.set(++timerId, () => callback(...args)); return timerId; },
        clearTimeout(id) { timers.delete(id); }
    });
    if (!pageSources.has(relativePath)) pageSources.set(relativePath, fs.readFileSync(path.join(__dirname, relativePath), 'utf8'));
    const html = pageSources.get(relativePath);
    for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
        if (match[1].trim()) vm.runInContext(match[1], context, {filename: relativePath});
    }
    for (const listener of readyListeners) listener();
    return {context, element, document, downloads, messages, flushTimers() {
        const pending = [...timers.values()];
        timers.clear();
        for (const callback of pending) callback();
    }};
}

function createZipRuntime(onClose = () => {}) {
    return {
        BlobReader: class {constructor(data) {this.data = data;}},
        TextWriter: class {}, BlobWriter: class {},
        ZipReader: class {
            constructor(reader) {this.data = reader.data;}
            async getEntries() {return this.data.getEntries ? this.data.getEntries() : this.data.entries;}
            async close() {onClose();}
        }
    };
}

const entry = (filename, text, uncompressedSize) => ({filename, uncompressedSize, getData: async () => text});
const stats = (design, current = 4500) => `Statistics since last charge:\nEstimated battery capacity: ${design} mAh\nMin learned battery capacity: ${current} mAh\n\n`;
const reportFile = (name = 'report.zip', model = 'Synthetic Device', design = 5000) => ({name, size: 1, entries: [
    entry('android.hardware.health.txt', `batteryFullChargeDesignCapacityUah: ${design * 1000}\n`),
    entry('bugreport.txt', `[ro.product.model]: [${model}]\n` + stats(5000))
]});

function trackWork(page, name, action) {
    const original = page.context[name];
    let work;
    page.context[name] = (...args) => {work = original(...args); return work;};
    try {action();} finally {page.context[name] = original;}
    return work;
}

async function choose(page, file) {
    page.element('zip-file').files = [file];
    return trackWork(page, page.context.extractDeviceInfo ? 'extractDeviceInfo' : 'parseZipAndRender',
        () => page.element('zip-file').dispatchEvent({type: 'change'}));
}

async function recalculate(page) {
    return trackWork(page, page.context.extractDeviceInfo ? 'processZipFile' : 'parseZipAndRender',
        () => page.element('calculate-btn').click());
}

function capacityInput(page, value) {
    page.element('initial-capacity').value = value;
    page.element('initial-capacity').dispatchEvent({type: 'input'});
}

function delayedEntry() {
    let resolve, reject;
    const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
    const control = {started: false, resolve, reject};
    control.entry = {filename: 'bugreport.txt', getData() {control.started = true; return promise;}};
    return control;
}

async function waitForRead(control) {
    for (let i = 0; i < 50 && !control.started; i++) await Promise.resolve();
    assert.ok(control.started, 'The deferred ZIP read must start before input changes');
}

async function runExportRegressions() {
    let assertions = 0, failures = 0, cases = 0;
    const check = Object.fromEntries(['equal', 'deepEqual', 'ok', 'match', 'doesNotMatch'].map(method => [method, (...args) => {
        assert[method](...args);
        assertions++;
    }]));
    async function run(name, task) {
        cases++;
        try {await task();} catch (error) {failures++; console.error(`FAIL: ${name}\n${error.stack}`);}
    }
    function fixture(name) {
        const page = loadPage(name);
        page.closed = 0;
        page.context.zip = createZipRuntime(() => page.closed++);
        return page;
    }
    function assertNoDownload(page) {
        check.equal(page.downloads.created.length, 0, 'Invalid reports must not create a Blob URL');
        check.equal(page.downloads.anchors.length, 0, 'Invalid reports must not create a download anchor');
    }
    async function download(page) {
        const previous = page.downloads.requests.length;
        page.element('export-report-btn').click();
        check.equal(page.downloads.requests.length, previous + 1, 'The report must be downloadable');
        const request = page.downloads.requests.at(-1);
        check.ok(request.blob instanceof Blob, 'Inspect the actual Blob passed to createObjectURL');
        const bytes = Buffer.from(await request.blob.arrayBuffer());
        return {...request, bytes, text: bytes.subarray(3).toString('utf8')};
    }
    function assertCleanedUp(page) {
        check.equal(page.document.body.children.length, 0, 'Temporary anchors must leave the document');
        check.ok(page.downloads.anchors.every(anchor => anchor.parentNode === null));
        page.flushTimers();
        check.deepEqual(page.downloads.revoked, page.downloads.created.map(item => item.url), 'Every created URL must be revoked exactly once');
        check.equal(page.downloads.active.size, 0, 'No object URLs may remain live after cleanup');
    }

    for (const name of pages) {
        for (const change of ['capacity', 'same-metadata file replacement', 'file removal']) {
            await run(`${name}: ${change} without an input/change event`, async () => {
                const page = fixture(name);
                const file = reportFile();
                await choose(page, file);
                check.equal(page.element('export-report-btn').disabled, false);
                if (change === 'capacity') page.element('initial-capacity').value = '6000';
                else page.element('zip-file').files = change === 'file removal' ? [] : [{...file}];
                page.context.saveReportAsTxt();
                check.equal(page.element('export-report-btn').disabled, true);
                assertNoDownload(page);
            });
        }

        for (const change of ['capacity event', 'capacity without event', 'file without event']) {
            await run(`${name}: pending analysis cannot export after ${change}`, async () => {
                const page = fixture(name);
                const delayed = delayedEntry();
                const pending = choose(page, {name: 'pending.zip', size: 1, entries: [delayed.entry]});
                await waitForRead(delayed);
                if (change === 'capacity event') capacityInput(page, '6000');
                else if (change === 'capacity without event') page.element('initial-capacity').value = '6000';
                else page.element('zip-file').files = [reportFile('replacement.zip')];
                check.equal(page.element('export-report-btn').disabled, true);
                delayed.resolve(stats(5000));
                await pending;
                check.equal(page.element('export-report-btn').disabled, true, 'Stale completion must not re-enable export');
                page.context.saveReportAsTxt();
                assertNoDownload(page);
            });
        }

        for (const completion of ['resolve', 'reject']) {
            await run(`${name}: old ${completion} cannot replace or invalidate a newer export`, async () => {
                const page = fixture(name);
                const delayed = delayedEntry();
                const pending = choose(page, {name: 'old.zip', size: 1, entries: [delayed.entry]});
                await waitForRead(delayed);
                await choose(page, reportFile('new.zip', 'New Export Device'));
                const expected = page.element('result').innerHTML;
                delayed[completion](completion === 'resolve' ? '[ro.product.model]: [Old Export Device]\n' + stats(5000, 4000) : new Error('synthetic stale read failure'));
                await pending;
                check.equal(page.element('result').innerHTML, expected);
                check.equal(page.element('export-report-btn').disabled, false);
                const saved = await download(page);
                check.match(saved.text, /New Export Device/);
                check.doesNotMatch(saved.text, /Old Export Device/);
                assertCleanedUp(page);
            });
        }

        await run(`${name}: clearing a manual override restores detected hardware capacity`, async () => {
            const page = fixture(name);
            await choose(page, reportFile('hardware.zip', 'Capacity Device', 5100));
            check.match(page.element('result').textContent, /5100 mAh/);
            capacityInput(page, '6000');
            check.equal(page.element('export-report-btn').disabled, true);
            await recalculate(page);
            check.match(page.element('result').textContent, /6000 mAh/);
            check.match(page.element('result').textContent, /75\.00%/);
            capacityInput(page, '');
            await recalculate(page);
            const restored = await download(page);
            check.match(restored.text, /5100 mAh/);
            check.match(restored.text, /88\.24%/);
            check.match(restored.text, /hardware health/);
            check.doesNotMatch(page.element('result').textContent, /6000 mAh/);
            check.equal(page.closed, 1, 'Override changes must reuse parsed data');
            assertCleanedUp(page);
        });

        await run(`${name}: TXT bytes preserve blocks and omit controls`, async () => {
            const page = fixture(name);
            const title = '\u7535\u6c60\u62a5\u544a';
            const markup = `<section><h2>${title}</h2><p>first &amp; &lt;sample&gt;</p><div>second<br>third</div>` +
                '<ul><li>one</li><li>two</li></ul><table><tr><th>Key</th><th>Value</th></tr><tr><td>Capacity</td><td>5000</td></tr></table>' +
                '<pre>raw-a\nraw-b\rraw-c\r\nraw-d</pre><button>TOGGLE_LABEL<span>BUTTON_CHILD</span></button>' +
                '<script>SCRIPT_LABEL</script><style>STYLE_LABEL</style></section>';
            page.element('zip-file').files = [reportFile('format.zip')];
            page.context.setExportReport(markup, 'format.zip', {});
            const saved = await download(page);
            check.deepEqual([...saved.bytes.subarray(0, 3)], [0xef, 0xbb, 0xbf], 'TXT must begin with the UTF-8 BOM bytes');
            check.equal(saved.blob.type, 'text/plain;charset=utf-8');
            const expectedBody = [title, 'first & <sample>', 'second', 'third', 'one', 'two', 'Key\tValue', 'Capacity\t5000', 'raw-a', 'raw-b', 'raw-c', 'raw-d', ''].join('\r\n');
            check.equal(saved.text.slice(saved.text.indexOf('\r\n\r\n') + 4), expectedBody);
            check.doesNotMatch(saved.text.replaceAll('\r\n', ''), /[\r\n]/, 'All line endings must be CRLF');
            check.doesNotMatch(saved.text, /TOGGLE_LABEL|BUTTON_CHILD|SCRIPT_LABEL|STYLE_LABEL/);
            assertCleanedUp(page);
            check.equal(page.element('export-report-btn').disabled, false);
        });

        await run(`${name}: failed anchor click releases resources and allows retry`, async () => {
            const page = fixture(name);
            await choose(page, reportFile());
            page.downloads.clickError = new Error('synthetic download click failure');
            page.element('export-report-btn').click();
            check.equal(page.downloads.created.length, 1);
            check.equal(page.downloads.attempts.length, 1);
            check.equal(page.downloads.requests.length, 0);
            check.match(page.element('status').textContent, /synthetic download click failure/);
            check.equal(page.element('export-report-btn').disabled, false, 'A failed download must permit retry');
            assertCleanedUp(page);
            page.downloads.clickError = null;
            const retried = await download(page);
            check.equal(page.downloads.created.length, 2);
            check.deepEqual(retried.bytes, Buffer.from(await page.downloads.created[0].blob.arrayBuffer()), 'Retry must preserve the original report bytes');
            assertCleanedUp(page);
        });

        await run(`${name}: download filenames are sanitized and bounded`, async () => {
            const page = fixture(name);
            for (const source of ['bad\u0000\u001f\u007f\\/:*?"<>| name.ZIP', '\u{1f50b}'.repeat(120) + '.zip', '', '.zip', 'CON.zip']) {
                page.element('zip-file').files = [reportFile(source)];
                page.context.setExportReport('<p>Filename fixture</p>', source, {});
                const saved = await download(page);
                check.doesNotMatch(saved.filename, /[\u0000-\u001f\u007f\\/:*?"<>|\s]/);
                check.match(saved.filename, /^.+_\d{14}\.txt$/);
                check.ok(Array.from(saved.filename).length <= 119, 'Base must be bounded to 100 Unicode code points');
                check.ok(saved.filename.length <= 219, 'Supplementary characters must also fit a Windows filename');
                check.equal(Buffer.from(saved.filename).toString('utf8'), saved.filename, 'Truncation must not split surrogate pairs');
                check.doesNotMatch(saved.filename, /\.zip_\d/i);
            }
            assertCleanedUp(page);
        });

        await run(`${name}: oversized inner ZIPs are skipped and counted in the report`, async () => {
            const page = fixture(name);
            let reads = 0;
            const file = reportFile();
            file.entries.unshift(...[1, 2].map(n => ({filename: `oversized-${n}.zip`, uncompressedSize: 512 * 1024 * 1024 + n, getData() {reads++; throw new Error('Oversized ZIP must not be read');}})));
            await choose(page, file);
            check.equal(reads, 0);
            check.equal(page.closed, 1, 'Skipped ZIPs must not open inner readers');
            const saved = await download(page);
            check.match(saved.text, /\uff082 \u5904\uff09/, 'Both skipped ZIPs must contribute to the visible warning count');
            check.match(saved.text, /90\.00%/);
            assertCleanedUp(page);
        });

        for (const nested of [false, true]) {
            await run(`${name}: ${nested ? 'nested' : 'top-level'} 256 MiB text boundary and pre-read rejection`, async () => {
                const page = fixture(name);
                let allowedReads = 0, oversizedReads = 0;
                const candidates = [
                    ['android.hardware.health.txt', 'batteryFullChargeDesignCapacityUah: 5100000\n'],
                    ['bugreport.txt', '[ro.product.model]: [Boundary Device]\n' + stats(5000)]
                ].flatMap(([filename, text]) => [
                    {filename, uncompressedSize: 256 * 1024 * 1024, async getData() {allowedReads++; return text;}},
                    {filename: 'oversized-' + filename, uncompressedSize: 256 * 1024 * 1024 + 1, async getData() {oversizedReads++; return 'OVERSIZED_CONTENT_MUST_NOT_APPEAR';}}
                ]);
                await choose(page, {name: 'limits.zip', size: 1, entries: nested ? [entry('inner.zip', {entries: candidates})] : candidates});
                check.equal(oversizedReads, 0, 'Oversized health and bugreport text must be rejected before getData');
                check.equal(allowedReads, 2, 'Exactly 256 MiB must remain readable');
                check.equal(page.closed, nested ? 2 : 1);
                const saved = await download(page);
                check.match(saved.text, /Boundary Device/);
                check.match(saved.text, /88\.24%/);
                check.match(saved.text, /\uff082 \u5904\uff09/);
                check.doesNotMatch(saved.text, /OVERSIZED_CONTENT_MUST_NOT_APPEAR/);
                assertCleanedUp(page);
            });
        }
    }

    for (const missing of ['design capacity', 'current capacity']) {
        await run(`portable: partial report with missing ${missing} remains saveable`, async () => {
            const page = fixture('HyperBatteryHealthCalc-bat/index.html');
            const snapshot = '[ro.product.model]: [Partial Export Device]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n';
            await choose(page, {name: 'partial.zip', size: 1, entries: [entry('bugreport.txt', snapshot + (missing === 'current capacity' ? stats(5000, 0) : ''))]});
            check.equal(page.element('result').className, 'result error');
            check.equal(page.element('export-report-btn').disabled, false);
            const saved = await download(page);
            check.match(saved.text, /Partial Export Device/);
            check.match(saved.text, /34\.5/);
            check.match(saved.text, /1000 mAh/);
            check.doesNotMatch(saved.text, /NaN|Infinity/);
            assertCleanedUp(page);
        });
    }

    for (const omission of ['oversized inner ZIP', 'corrupt inner blob', 'corrupt inner directory']) {
        await run(`root: manual retry reports ${omission} after initial read failure`, async () => {
            const page = fixture('index.html');
            let attempts = 0, innerReads = 0;
            const file = reportFile('retry-with-omission.zip');
            file.entries.unshift({
                filename: 'omitted.zip',
                uncompressedSize: omission === 'oversized inner ZIP' ? 512 * 1024 * 1024 + 1 : 1,
                getData() {
                    innerReads++;
                    if (omission === 'corrupt inner directory') {
                        return {getEntries() {throw new Error('synthetic inner directory failure');}};
                    }
                    throw new Error('synthetic inner blob failure');
                }
            });
            file.getEntries = () => {if (++attempts === 1) throw new Error('synthetic initial directory failure'); return file.entries;};
            await choose(page, file);
            capacityInput(page, '5000');
            await recalculate(page);
            check.equal(attempts, 2, 'The manual retry must exercise the uncached calculation path');
            check.equal(innerReads, omission === 'oversized inner ZIP' ? 0 : 1);
            check.equal(page.closed, omission === 'corrupt inner directory' ? 3 : 2, 'Failed readers must still close');
            check.match(page.element('result').textContent, /\uff081 \u5904\uff09/, 'The rendered report must disclose the omitted ZIP');
            check.match(page.element('result').textContent, /90\.00%/);
            const saved = await download(page);
            check.match(saved.text, /90\.00%/);
            assertCleanedUp(page);
            check.match(saved.text, /\uff081 \u5904\uff09/, 'The exported report must disclose the omitted ZIP');
            await recalculate(page);
            check.equal(attempts, 3, 'A repeated retry must read the archive again');
            check.match(page.element('result').textContent, /\uff081 \u5904\uff09/, 'Warning counts must reset before another retry');
            const repeated = await download(page);
            check.match(repeated.text, /\uff081 \u5904\uff09/, 'Repeated exports must not accumulate warning counts');
            assertCleanedUp(page);
        });
    }

    console.log(`${failures ? 'FAIL' : 'PASS'}: ${assertions} export/input/ZIP assertions across ${cases} cases; ${failures} failed cases`);
    return failures;
}

async function runRootPartialReportRegressions() {
    let assertions = 0;
    const equal = (actual, expected, message) => {assert.equal(actual, expected, message); assertions++;};
    const match = (actual, expected, message) => {assert.match(actual, expected, message); assertions++;};
    const snapshot = '[ro.product.model]: [Partial Snapshot]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n';
    const setup = () => {
        const page = loadPage('index.html');
        page.context.zip = createZipRuntime();
        return page;
    };
    const verifyPartialDownload = async (page, label) => {
        equal(page.element('export-report-btn').disabled, false, label);
        equal(page.element('export-report-btn').style.display, 'block', label);
        const previous = page.downloads.requests.length;
        page.context.saveReportAsTxt();
        equal(page.downloads.requests.length, previous + 1, label);
        const saved = await page.downloads.requests.at(-1).blob.text();
        match(saved, /\u90e8\u5206\u6570\u636e/, label);
        match(saved, /34\.5/, label);
        match(saved, /1000 mAh/, label);
        page.flushTimers();
        equal(page.downloads.active.size, 0, label);
        equal(page.document.body.children.length, 0, label);
    };

    const missingDesign = setup();
    await choose(missingDesign, {name: 'missing-design.zip', size: 1, entries: [entry('bugreport.txt', snapshot)]});
    await verifyPartialDownload(missingDesign, 'Initial partial report without design capacity');
    missingDesign.element('initial-capacity').value = '5000';
    const downloadsBeforeInvalidation = missingDesign.downloads.requests.length;
    missingDesign.context.saveReportAsTxt();
    equal(missingDesign.element('export-report-btn').disabled, true, 'Changed input invalidates partial export');
    equal(missingDesign.downloads.requests.length, downloadsBeforeInvalidation, 'No stale partial download');
    await missingDesign.context.calculateBatteryCapacity();
    await verifyPartialDownload(missingDesign, 'Cached partial report after manual capacity');

    const missingCurrent = setup();
    await choose(missingCurrent, {name: 'missing-current.zip', size: 1, entries: [
        entry('android.hardware.health.txt', 'batteryFullChargeDesignCapacityUah: 5000000\n'),
        entry('bugreport.txt', snapshot + stats(5000, 0))
    ]});
    await verifyPartialDownload(missingCurrent, 'Automatic cached report without current capacity');

    const retry = setup();
    let attempts = 0;
    const retryFile = {name: 'partial-retry.zip', size: 1, getEntries() {
        if (++attempts === 1) throw new Error('Synthetic initial directory failure');
        return [entry('bugreport.txt', snapshot + stats(5000, 0))];
    }};
    await choose(retry, retryFile);
    equal(retry.element('export-report-btn').disabled, true, 'Directory failure has no export');
    retry.element('initial-capacity').value = '5000';
    await retry.context.calculateBatteryCapacity();
    await verifyPartialDownload(retry, 'Partial report from a successful manual retry');
    equal(attempts, 2, 'Retry actually reopens the archive');

    for (const candidate of [entry('bugreport.txt', ''), {filename: 'bugreport.txt', getData: async () => {throw new Error('Synthetic corrupt entry');}}]) {
        const invalid = setup();
        await choose(invalid, {name: 'unusable.zip', size: 1, entries: [candidate]});
        equal(invalid.element('export-report-btn').disabled, true, 'Empty or unreadable logs cannot be exported');
        invalid.element('initial-capacity').value = '5000';
        await invalid.context.calculateBatteryCapacity();
        equal(invalid.element('export-report-btn').disabled, true, 'Manual input alone is not extracted diagnostic data');
        invalid.context.saveReportAsTxt();
        equal(invalid.downloads.requests.length, 0, 'No download without extracted data');
    }
    console.log(`PASS: ${assertions} root partial-report assertions`);
}

async function runRealZipCrcRegressions() {
    let assertions = 0, failures = 0, cases = 0;
    const check = Object.fromEntries(['equal', 'deepEqual', 'ok', 'match', 'doesNotMatch'].map(method => [method, (...args) => {
        assert[method](...args);
        assertions++;
    }]));
    const {createHash} = require('node:crypto');
    const runtimePaths = ['js/zip.min.js', 'HyperBatteryHealthCalc-bat/js/zip.min.js'].map(name => path.join(__dirname, name));
    const runtimeHashes = runtimePaths.map(name => createHash('sha256').update(fs.readFileSync(name)).digest('hex'));
    check.equal(runtimeHashes[0], runtimeHashes[1], 'Both pages must use identical zip.js bytes before sharing a real runtime');
    const realZip = require(runtimePaths[0]);
    realZip.configure({useWebWorkers: false});

    async function archive(records) {
        const writer = new realZip.ZipWriter(new realZip.Uint8ArrayWriter(), {level: 0, dataDescriptor: false});
        for (const [name, value] of records) {
            const reader = typeof value === 'string' ? new realZip.TextReader(value) : new realZip.Uint8ArrayReader(value);
            await writer.add(name, reader);
        }
        return new Uint8Array(await writer.close());
    }
    function corruptContent(bytes, original, replacement) {
        const before = Buffer.from(original), after = Buffer.from(replacement);
        check.equal(before.length, after.length, 'Payload mutation must preserve ZIP offsets and sizes');
        check.ok(!before.equals(after), 'The corruption fixture must actually change payload bytes');
        const changed = new Uint8Array(bytes);
        const offset = Buffer.from(changed).indexOf(before);
        check.ok(offset >= 0, 'The library-generated stored ZIP must contain the target plaintext');
        changed.set(after, offset);
        return changed;
    }
    function corruptCentralCrc(bytes, filename) {
        // Change only the selected entry CRC, keeping nested ZIP bytes intact.
        const changed = Buffer.from(bytes);
        const end = changed.length - 22;
        check.equal(changed.readUInt32LE(end), 0x06054b50, 'Fixtures have a normal EOCD and no archive comment');
        const count = changed.readUInt16LE(end + 10);
        let offset = changed.readUInt32LE(end + 16);
        for (let i = 0; i < count; i++) {
            check.equal(changed.readUInt32LE(offset), 0x02014b50, 'Locate a real central-directory record');
            const nameLength = changed.readUInt16LE(offset + 28);
            const name = changed.subarray(offset + 46, offset + 46 + nameLength).toString('utf8');
            if (name === filename) {
                changed.writeUInt32LE((changed.readUInt32LE(offset + 16) ^ 1) >>> 0, offset + 16);
                return new Uint8Array(changed);
            }
            offset += 46 + nameLength + changed.readUInt16LE(offset + 30) + changed.readUInt16LE(offset + 32);
        }
        throw new Error('Synthetic CRC target not found: ' + filename);
    }
    async function verifyFixture(bytes, filename, expected, corrupt) {
        const reader = new realZip.ZipReader(new realZip.Uint8ArrayReader(bytes));
        try {
            const candidate = (await reader.getEntries()).find(item => item.filename === filename);
            check.ok(candidate, 'The targeted synthetic entry must exist');
            const actual = await candidate.getData(new realZip.Uint8ArrayWriter(), {checkSignature: !corrupt});
            check.deepEqual(Buffer.from(actual), Buffer.from(expected), 'The fixture must remain structurally readable');
            if (corrupt) {
                await assert.rejects(candidate.getData(new realZip.Uint8ArrayWriter(), {checkSignature: true}), /Invalid signature/);
                assertions++;
            }
        } finally {
            await reader.close();
        }
    }

    const snapshot = model => `[ro.product.model]: [${model}]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n`;
    const goodPartial = snapshot('Valid CRC Device');
    const goodHealth = 'batteryFullChargeDesignCapacityUah: 5000000\nbatteryCycleCount: 42\n';
    const goodRecords = [['android.hardware.health-valid.txt', goodHealth], ['bugreport-valid.txt', goodPartial + stats(5000)]];
    const badHealth = 'batteryFullChargeDesignCapacityUah: 9000000\nbatteryCycleCount: 99999\n';
    const changedHealth = badHealth.replace('9000000', '8000000');
    const badPartial = snapshot('CRC_REJECTED_DEVICE');
    const changedPartial = badPartial.replace('temperature: 345', 'temperature: 355');
    const healthRecord = ['android.hardware.health-corrupt.txt', badHealth];
    const bugreportRecord = ['bugreport-corrupt.txt', badPartial];
    const goodArchive = await archive(goodRecords);
    const nestedGood = await archive([['inner.zip', goodArchive]]);
    const partialArchive = await archive([['bugreport-valid.txt', goodPartial]]);
    const badHealthOnly = corruptContent(await archive([healthRecord]), badHealth, changedHealth);
    const badBugreportOnly = corruptContent(await archive([bugreportRecord]), badPartial, changedPartial);
    const badHealthThenGood = corruptContent(await archive([healthRecord, ...goodRecords]), badHealth, changedHealth);
    const badBugreportThenGood = corruptContent(await archive([bugreportRecord, ['bugreport-valid.txt', goodPartial]]), badPartial, changedPartial);
    const goodThenBadPartial = corruptContent(await archive([['bugreport-valid.txt', goodPartial], bugreportRecord]), badPartial, changedPartial);

    const poisonText = changedPartial + stats(5000);
    const validPoisonInner = await archive([['bugreport-inner.txt', poisonText]]);
    const badOuter = corruptCentralCrc(await archive([['inner.zip', validPoisonInner], ...goodRecords]), 'inner.zip');
    const badInnerText = corruptCentralCrc(await archive([['bugreport-corrupt.txt', poisonText], ...goodRecords]), 'bugreport-corrupt.txt');
    const checkedOuterBadText = await archive([['inner.zip', badInnerText]]);
    const badInnerHealth = corruptCentralCrc(await archive([['android.hardware.health-corrupt.txt', changedHealth], ...goodRecords]), 'android.hardware.health-corrupt.txt');
    const checkedOuterBadHealth = await archive([['inner.zip', badInnerHealth]]);

    await verifyFixture(goodArchive, 'bugreport-valid.txt', goodPartial + stats(5000), false);
    await verifyFixture(badHealthOnly, healthRecord[0], changedHealth, true);
    await verifyFixture(badBugreportOnly, bugreportRecord[0], changedPartial, true);
    await verifyFixture(validPoisonInner, 'bugreport-inner.txt', poisonText, false);
    await verifyFixture(badOuter, 'inner.zip', validPoisonInner, true);
    await verifyFixture(checkedOuterBadText, 'inner.zip', badInnerText, false);
    await verifyFixture(badInnerText, 'bugreport-corrupt.txt', poisonText, true);
    await verifyFixture(checkedOuterBadHealth, 'inner.zip', badInnerHealth, false);
    await verifyFixture(badInnerHealth, 'android.hardware.health-corrupt.txt', changedHealth, true);

    const forbidden = /CRC_REJECTED_DEVICE|35\.5|8000 mAh|99999/;
    const warning = count => new RegExp('\\uff08' + count + ' \\u5904\\uff09');
    async function inspectReport(page, {full = false, warnings = 0, rejected = false}) {
        const rendered = page.element('result').textContent;
        check.doesNotMatch(rendered, forbidden, 'CRC-rejected data must never reach the visible report');
        check.equal(page.element('export-report-btn').disabled, rejected, 'Only verified extracted data may be exported');
        const previous = page.downloads.requests.length;
        page.context.saveReportAsTxt();
        check.equal(page.downloads.requests.length, previous + (rejected ? 0 : 1));
        if (rejected) {
            check.equal(page.downloads.created.length, 0, 'Rejected archives must not create download URLs');
            check.equal(page.downloads.anchors.length, 0, 'Rejected archives must not create download anchors');
            return;
        }
        const blob = page.downloads.requests.at(-1).blob;
        check.ok(blob instanceof Blob, 'Inspect the actual report Blob');
        const saved = await blob.text();
        for (const text of [rendered, saved]) {
            check.match(text, /Valid CRC Device/, 'A later valid candidate must remain available');
            check.match(text, /34\.5/, 'Keep the verified snapshot temperature');
            check.match(text, /1000 mAh/, 'Keep the verified charge-counter snapshot');
            check.doesNotMatch(text, forbidden, 'Corrupt candidates cannot contaminate display or export');
            if (full) check.match(text, /90\.00%/);
            if (warnings) check.match(text, warning(warnings), 'Disclose every rejected CRC candidate');
            else check.doesNotMatch(text, /\uff08\d+ \u5904\uff09/, 'Valid ZIPs must not acquire CRC warnings');
        }
        page.flushTimers();
        check.equal(page.downloads.active.size, 0);
        check.equal(page.document.body.children.length, 0);
    }
    async function run(pageName, label, bytes, expected, manual = false) {
        cases++;
        try {
            const page = loadPage(pageName);
            page.context.zip = realZip;
            const file = new Blob([bytes], {type: 'application/zip'});
            Object.defineProperty(file, 'name', {value: 'synthetic-crc-' + cases + '.zip'});
            if (manual) {
                // No extraction cache: exercise the root retry reader with real ZIP bytes.
                page.element('zip-file').files = [file];
                capacityInput(page, '5000');
                await page.context.calculateBatteryCapacity();
            } else {
                await choose(page, file);
            }
            await inspectReport(page, expected);
        } catch (error) {
            failures++;
            console.error(`FAIL: ${pageName}: ${label}\n${error.stack}`);
        }
    }
    for (const pageName of pages) {
        await run(pageName, 'valid plain archive', goodArchive, {full: true});
        await run(pageName, 'valid nested archive', nestedGood, {full: true});
        await run(pageName, 'valid partial archive', partialArchive, {});
        await run(pageName, 'corrupted plain health only', badHealthOnly, {rejected: true});
        await run(pageName, 'corrupted plain bugreport only', badBugreportOnly, {rejected: true});
        await run(pageName, 'corrupted health before valid candidates', badHealthThenGood, {full: true, warnings: 1});
        await run(pageName, 'corrupted bugreport before valid partial', badBugreportThenGood, {warnings: 1});
        await run(pageName, 'valid partial followed by corrupt partial', goodThenBadPartial, {warnings: 1});
        await run(pageName, 'bad outer CRC with independently valid inner ZIP', badOuter, {full: true, warnings: 1});
        await run(pageName, 'valid outer CRC with bad inner bugreport then valid candidates', checkedOuterBadText, {full: true, warnings: 1});
        await run(pageName, 'valid outer CRC with bad inner health then valid candidates', checkedOuterBadHealth, {full: true, warnings: 1});
    }
    await run('index.html', 'uncached manual path accepts valid nested ZIP', nestedGood, {full: true}, true);
    await run('index.html', 'uncached manual path rejects outer CRC before later valid candidate', badOuter, {full: true, warnings: 1}, true);
    await run('index.html', 'uncached manual path rejects inner text CRC before later valid candidate', checkedOuterBadText, {full: true, warnings: 1}, true);
    console.log(`${failures ? 'FAIL' : 'PASS'}: ${assertions} real zip.js CRC assertions across ${cases} cases; ${failures} failed cases; runtime SHA256 ${runtimeHashes[0]}`);
    return failures;
}

async function main() {
    let assertions = 0;
    for (const page of ['index.html', 'HyperBatteryHealthCalc-bat/index.html']) {
        const {context} = loadPage(page);
        const cases = [
            [{minLearnedCapacity: 0, chargeCounter: 4500, batteryLevel: 100}, 4500],
            [{minLearnedCapacity: -1, chargeCounter: 4500, batteryLevel: 100}, 4500],
            [{chargeCounter: 4500, batteryLevel: 100, batteryScale: 200}, null],
            [{chargeCounter: 4500, batteryLevel: 10, batteryScale: 10}, 4500],
            [{chargeCounter: 4500, batteryLevel: 101, batteryScale: 100}, null],
            // Parity with Python round(): 4599.8 mAh -> 4600
            [{minLearnedCapacity: 4600, chargeCounter: 4500, batteryLevel: 100}, 4600]
        ];
        for (const [info, expected] of cases) {
            assert.equal(context.getCurrentCapacityInfo(info).value, expected, page);
            assertions++;
        }
        assert.equal(context.parseDurationSeconds('1h2m3s4ms'), 3723.004, page);
        assert.equal(context.parseDurationSeconds('1d2h3m4s'), 93784, page);
        const usage = {};
        context.parseUsageStats('Time on battery: 1d2h3m4s (100.0%) realtime', usage);
        assert.equal(usage.timeOnBatterySeconds, 93784, page);
        assertions += 3;
        const power = {uidPackages:{}};
        context.parsePowerUseStats('UID unrelated: 9999\nGlobal\n    cpu: 9999\n\nEstimated power use (mAh):\n  Capacity: 5000, Computed drain: 600, actual drain: 600\n  Global\n    cpu: 120\n  UID real: 80\n\nUID unrelated-after: 8888\n', power);
        assert.equal(power.topUidPower[0].uid, 'real', page);
        assert.equal(power.powerComponents[0].mah, 120, page);
        assertions += 2;
    }

    const {context, element} = loadPage('HyperBatteryHealthCalc-bat/index.html');
    let closed = 0;
    context.zip = createZipRuntime(() => closed++);
    const file = {name: 'report.zip', size: 1, entries: [
        entry('bugreport.txt', 'Statistics since last charge:\nEstimated battery capacity: 5000 mAh\nMin learned battery capacity: 4500 mAh\n\n'),
        entry('android.hardware.health.txt', 'batteryFullChargeDesignCapacityUah: 5100000\nbatteryCycleCount: 123\n')
    ]};
    await context.parseZipAndRender(file, 6000);
    assert.match(element('result').innerHTML, /6000/);
    assert.match(element('result').innerHTML, /123/);
    assert.match(element('result').innerHTML, /75\.00/);
    assert.equal(closed, 1);
    assertions += 4;
    await context.parseZipAndRender(file, 5000);
    assert.equal(closed, 1, 'manual recalculation must reuse parsed data');
    assert.match(element('result').innerHTML, /90\.00/);
    assertions += 2;

    const root = loadPage('index.html');
    root.context.zip = context.zip;
    root.element('zip-file').files = [file];
    const beforeRoot = closed;
    await root.context.extractDeviceInfo(file);
    assert.equal(closed - beforeRoot, 1, 'root auto analysis must not decompress a second time');
    root.element('initial-capacity').value = '6000';
    await root.context.calculateBatteryCapacity();
    assert.match(root.element('result').innerHTML, /75\.00/);
    assert.equal(closed - beforeRoot, 1, 'root manual calculation must use cached data');
    assert.equal(root.context.getAutoInitialCapacityCandidate({minLearnedCapacity:4500, lastLearnedCapacity:4600}), null);
    assertions += 4;

    for (const name of ['index.html', 'HyperBatteryHealthCalc-bat/index.html']) {
        const page=loadPage(name);
        page.context.zip=context.zip;
        await choose(page,{name:'valid.zip',size:1,entries:[
            entry('android.hardware.health-a.txt','batteryFullChargeDesignCapacityUah: 5000000\n'),
            entry('android.hardware.health-b.txt','batteryFullChargeDesignCapacityUah: 0\n'),
            entry('bugreport.txt',stats(5000))
        ]});
        assert.match(page.element('result').innerHTML,/90\.00%/, name);
        await choose(page,{name:'partial.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [Snapshot Device]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n'+stats(5000,0))]});
        assert.match(page.element('result').innerHTML,/34\.5/,name);
        assert.match(page.element('result').innerHTML,/1000 mAh/,name);
        let release;
        const old = choose(page,{name:'old.zip',size:1,entries:[{filename:'bugreport.txt',getData:()=>new Promise(resolve=>{release=resolve;})}]});
        for(let i=0;i<10&&!release;i++) await Promise.resolve();
        assert.ok(release);
        await choose(page,{name:'new.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [New Device]\n'+stats(5000))]});
        const expected=page.element('result').innerHTML;
        release('[ro.product.model]: [Old Device]\n'+stats(5000,4000));
        await old;
        assert.equal(page.element('result').innerHTML,expected,name);
        assertions += 5;
    }
    const retry=loadPage('index.html');
    retry.context.zip=context.zip;
    let attempts=0, releaseRetry;
    const failedFile={name:'retry.zip',size:1,getEntries(){if(++attempts===1) throw new Error('initial failure');return new Promise(resolve=>{releaseRetry=resolve;});}};
    await choose(retry,failedFile);
    retry.element('initial-capacity').value='5000';
    const pendingRetry=retry.context.processZipFile(failedFile,5000);
    assert.ok(releaseRetry);
    await choose(retry,{name:'new.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [New Device]\n'+stats(5000))]});
    const expected=retry.element('result').innerHTML;
    releaseRetry([]);
    await pendingRetry;
    assert.equal(retry.element('result').innerHTML,expected,'stale manual retry replaced current report');
    assertions += 2;
    const partialRetry=loadPage('index.html');
    partialRetry.context.zip=context.zip;
    await partialRetry.context.processZipFile({name:'partial.zip',size:1,entries:[entry('bugreport.txt','[ro.product.model]: [Partial Retry]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n\n'+stats(5000,0))]},5000);
    assert.match(partialRetry.element('result').innerHTML,/34\.5/);
    assert.match(partialRetry.element('result').innerHTML,/1000 mAh/);
    assertions += 2;
    console.log(`PASS: ${assertions} browser-logic assertions`);
    if (await runExportRegressions()) process.exitCode = 1;
    await runRootPartialReportRegressions();
    if (await runRealZipCrcRegressions()) process.exitCode = 1;
}
main().catch(error => {console.error(error); process.exitCode = 1;});
